import datetime

import logging
from collections.abc import Sequence

from django.db import transaction
from sao.models import (
    EmployeeDailyRecord,
    Employee,
    SteppingOut,
    EmployeeHour,
    WorkingHour,
    DaySwitchTime,
    DailyAttendanceRecord,
    WebTimeStamp,
    OvertimePermission,
    FixedOvertimePayEmployee,
)
from sao.const import Const
from sao.calendar import (
    is_holiday as calendar_is_holiday,
    is_legal_holiday,
    get_first_day,
    get_last_day,
    count_working_days,
    enumrate_days,
)
from sao.period import Period
from sao.working_status import WorkingStatus, determine_working_status
from sao.attendance import Attendance
from dateutil.relativedelta import relativedelta
from sao.exceptions import (
    NoAssignedWorkingHourError,
    AnomalyTimeRecordError,
    AnomalyAttendanceRecordError,
)

logger = logging.getLogger("sao")


def adjust_working_hours(
    work_hours: Period,
    status: int,
) -> Period:
    """午前休、午後休に応じて所定の勤務時間を調整する

    :param status: WorkingStatus
    :param working_hour: 所定の勤務時間
    :return: 調整後の勤務時間
    """

    duration = work_hours.duration()

    if is_need_break_time(duration, status):
        # 休息時間分を引く
        duration -= Const.TD_1H

    adjusted_start = work_hours.start
    adjusted_end = work_hours.end
    if status in WorkingStatus.MORNING_OFF:
        # 午前休なので開始時間を 所定労働時間の半分と休息１時間分ずらす
        adjusted_start = work_hours.start + duration / 2 + Const.TD_1H
    if status in WorkingStatus.AFTERNOON_OFF_WITH_REST:
        adjusted_end = work_hours.end - duration / 2
    elif status in WorkingStatus.AFTERNOON_OFF_NO_REST:
        # 休息なしなので休息１時間分ずらす
        adjusted_end = work_hours.end - duration / 2 - Const.TD_1H

    return Period(adjusted_start, adjusted_end)


def floor_to_30min(t: datetime.timedelta) -> datetime.timedelta:
    """
    30分単位で切り下げ
    例：1時間29分→1時間、1時間30分→1時間30分

    :param t: timedelta
    :return: 切り下げたtimedelta
    """
    return datetime.timedelta(seconds=t.total_seconds() // 1800 * 1800)


def round_to_half_hour(t: datetime.timedelta) -> datetime.timedelta:
    """30分未満は切り捨て、以上は切り上げ
    例：1時間20分→1時間、1時間30分→2時間

    :param t: timedelta
    :return: 四捨五入したtimedelta
    """
    if t.seconds % 3600 < 1800:
        return floor_to_30min(t)
    return datetime.timedelta(seconds=(t.total_seconds() // 3600 + 1) * 3600)


def round_attendance_summary(result: dict) -> dict:
    """
    勤怠集計結果を丸める
    30分単位で切り下げるものと、30分未満切り捨て、30分以上切り上げるものがある

    :param result: 勤怠集計結果
    :return: 丸めた勤怠集計結果
    """

    rounded = {}
    rounded["work"] = floor_to_30min(result["work"])
    rounded["late"] = floor_to_30min(result["late"])
    rounded["before"] = floor_to_30min(result["before"])
    rounded["steppingout"] = floor_to_30min(result["steppingout"])
    rounded["accumulated_overtime"] = floor_to_30min(result["accumulated_overtime"])

    # 時外勤、深夜、法定、所定は３０分未満切り下げ、３０分以上切り上げ       14/02/13
    rounded["out_of_time"] = round_to_half_hour(result["out_of_time"])
    rounded["night"] = round_to_half_hour(result["night"])
    rounded["legal_holiday"] = round_to_half_hour(result["legal_holiday"])
    rounded["holiday"] = round_to_half_hour(result["holiday"])
    # 151225 割増も切捨てではない
    rounded["over_8h"] = round_to_half_hour(result["over_8h"])

    return rounded


def adjust_work_start_time(
    clock_in: datetime.datetime, working_hours_start: datetime.datetime
) -> datetime.datetime:
    """
    始業時間を調整する

    - 遅刻してなければ所定の開始時間を返す
    - 遅刻してるなら打刻時間を返す
    - 打刻記録に出社の打刻がない場合はNoneを返す

    :param clock_in: 出社の打刻時間
    :param working_hours_start: 所定の勤務開始時間
    :return: 調整された勤務開始時間
    """

    if (clock_in - working_hours_start).days < 0:
        return working_hours_start
    # 遅刻している
    return clock_in


def adjust_work_end_time(
    clock_out: datetime.datetime,
    working_hours_end: datetime.datetime,
    overtime_permittion: bool,
) -> datetime.datetime | None:
    """
    終業時間を調整する
    - 残業許可なら打刻が退勤時刻になる
    - 早退している場合は打刻が退勤時刻になる
    - それ以外は所定の勤務終了時間になる
    - ※打刻がない場合はNoneを返す
    - ※所定の勤務終了時間がない場合はNoneを返す

    :param clock_out: 出社の打刻時間
    :param working_hours_end: 所定の勤務終了時間
    :param overtime_permittion: 残業許可があるかどうか
    :return: 調整された勤務終了時間
    """

    if (clock_out - working_hours_end).days < 0:
        # 早退
        return clock_out
    if overtime_permittion:
        # 残業OK
        return clock_out
    # 所定終業時間
    return working_hours_end


def calc_actual_working_hours(
    actual_working_hours: Period, status: int, steppingout: datetime.timedelta
) -> datetime.timedelta:
    """
    実際の労働時間の長さを計算する
    - 6時間を超える勤務なら休息時間分1時間を差し引く
    - 休息あり半休の場合は6時間以下でも休息時間分1時間を差し引く
    """

    duration = actual_working_hours.duration()
    if duration > Const.TD_6H:
        # 6時間を超えているので休息時間分を引く
        duration -= Const.TD_1H
    elif is_need_break_time(duration, status):
        duration -= Const.TD_1H
    return duration - steppingout


def calc_assumed_working_time(status: int, work_period: Period) -> datetime.timedelta:
    """想定されている実労働時間を計算する

    - 労働時間が６時間を超えるなら休息時間分が１時間引かれる
    - 打刻がない場合は０を返す
    - 勤務状態がない場合は０を返す

    :param status: 勤務状態
    :param work_period: 所定の勤務時間
    :return: 想定されている実労働時間
    """
    if work_period.is_unset():
        return Const.TD_ZERO
    if status is None:
        return Const.TD_ZERO
    duration = work_period.duration()
    if is_need_break_time(duration, status):
        duration -= Const.TD_1H
    return duration


def is_holidaywork(status: int) -> bool:
    """休日出勤かどうか"""
    if status is WorkingStatus.C_NONE:
        return False
    if status not in WorkingStatus.HOLIDAY_WORK:
        return False
    return True


def calc_tardiness(
    clock_in: datetime.datetime, work_start_time: datetime.datetime
) -> datetime.timedelta:
    """遅刻時間の計算

    :param clock_in: 出社の打刻時間
    :param work_start_time: 所定の勤務開始時間
    :return: 遅刻時間
    """
    d = clock_in - work_start_time
    return d if d.days >= 0 else Const.TD_ZERO


def calc_leave_early(
    clock_out: datetime.datetime, work_hours_end: datetime.datetime
) -> datetime.timedelta:
    """
    早退時間の計算
    もし退勤の打刻がない場合は早退もないこととする
    （その場合は不整合が発生するはず）
    """
    if work_hours_end < clock_out:
        # 早退ではない
        return Const.TD_ZERO
    return work_hours_end - clock_out


def calc_stepping_out(employee: Employee, stamp: Period) -> datetime.timedelta:
    """
    外出時間を集計する
    """
    if stamp.is_unset():
        return Const.TD_ZERO
    total_steppingout = Const.TD_ZERO
    so_employee = SteppingOut.objects.filter(employee=employee)
    so_period = so_employee.filter(out_time__gte=stamp.start, return_time__lt=stamp.end)
    for steppingout in so_period:
        total_steppingout += steppingout.duration()
    return total_steppingout


def tally_steppingout(
    employee: Employee,
    clock_in: datetime.datetime | None,
    clock_out: datetime.datetime | None,
) -> datetime.timedelta:
    """
    外出時間を集計する
    もし出勤/退勤の打刻がないばあいは0を返す
    """
    if clock_in is None or clock_out is None:
        return Const.TD_ZERO

    total_steppingout = Const.TD_ZERO
    for steppingout in SteppingOut.objects.filter(
        employee=employee,
        out_time__gte=clock_in,
        return_time__lt=clock_out,
    ):
        if steppingout.out_time is None or steppingout.return_time is None:
            continue
        total_steppingout += steppingout.return_time - steppingout.out_time
    return total_steppingout


def calc_overtime(
    actual_work: datetime.timedelta,
    work_hours: datetime.timedelta,
    is_overtime_permitted: bool,
) -> datetime.timedelta:
    """時間外勤務の時間を計算する
        休出は勤務時間超過がないのでここでは考慮しない

    - 所定勤務時間を超えた時間を返す
    - もし実勤務時間が所定勤務時間を超過していない場合は0を返す
    - 残業が認められていない場合は0を返す


    :param actual_work: 実労働時間
    :param work_hours: 所定の勤務時間
    :param is_overtime_permitted: 残業が認められているか
    :return: 時間外勤務時間
    """
    if not is_overtime_permitted:
        return Const.TD_ZERO
    if actual_work <= work_hours:
        return Const.TD_ZERO
    return actual_work - work_hours


def calc_over_8h(
    actual_work: datetime.timedelta, is_overtime_permitted: bool
) -> datetime.timedelta:
    """
    勤務時間が8時間を超過した時間を計算する
    - calc_overtimeと似ているが、こちらは8時間を超えた時間を返す
    - 残業が認められていない場合は0を返す
    :param record: EmployeeDailyRecord
    :param actual_work: 実労働時間
    :return: 8時間を超えた時間
    """
    if not is_overtime_permitted:
        return Const.TD_ZERO
    d = actual_work - Const.TD_8H
    return d if d.days >= 0 else Const.TD_ZERO


def calc_midnight_work(t: datetime.datetime) -> datetime.timedelta:
    """
    深夜超過時間
    - 深夜=22:00~

    :param t: datetime
    :return: 深夜超過時間
    """
    night = datetime.datetime.combine(t.date(), Const.NIGHT_WORK_START)
    duration = t - night
    return duration if duration.days >= 0 else Const.TD_ZERO


def summarize_attendance_days(
    results: list[Attendance], year_month: datetime.date
) -> list[int]:
    """
    日数算出
          戻り値は配列
          0 - 所定勤務日数
          1 - 出勤日数
          2 - 有給取得日数
          3 - 代休日数
          4 - 欠勤日数
          5 - 特別休暇日数
          6 - 遅刻回数
          7 - 早退回数    7 - 休日出勤日数
          8 - 休日出勤日数  8 - 有給残高
          9 - 有給残高
    """

    yuukyuu = [
        WorkingStatus.C_YUUKYUU,
        WorkingStatus.C_YUUKYUU_GOZENKYU,
        WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
        WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
    ]
    daikyuu = [
        WorkingStatus.C_DAIKYUU,
        WorkingStatus.C_DAIKYUU_GOZENKYU,
        WorkingStatus.C_DAIKYUU_GOGOKYUU_NASHI,
        WorkingStatus.C_DAIKYUU_GOGOKYUU_ARI,
    ]
    tokubetukyuu = [
        WorkingStatus.C_TOKUBETUKYUU,
        WorkingStatus.C_TOKUBETUKYUU_GOZENKYU,
        WorkingStatus.C_TOKUBETUKYUU_GOGOKYUU_NASHI,
        WorkingStatus.C_TOKUBETUKYUU_GOGOKYUU_ARI,
    ]
    days = [0, 0, 0, 0, 0, 0, 0, 0, 0]

    days[0] = count_working_days(year_month)  # 所定勤務日数

    for result in results:
        if result.late:
            days[6] += 1  # 遅刻回数

        if result.early_leave:
            days[7] += 1  # 早退回数

        # 平日出社
        if result.status == WorkingStatus.C_KINMU:
            days[1] += 1  # 出勤日数

        # 平日出社・半休
        if result.status in [
            WorkingStatus.C_YUUKYUU_GOZENKYU,
            WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
            WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
            WorkingStatus.C_DAIKYUU_GOZENKYU,
            WorkingStatus.C_DAIKYUU_GOGOKYUU_NASHI,
            WorkingStatus.C_DAIKYUU_GOGOKYUU_ARI,
            WorkingStatus.C_TOKUBETUKYUU_GOZENKYU,
            WorkingStatus.C_TOKUBETUKYUU_GOGOKYUU_NASHI,
            WorkingStatus.C_TOKUBETUKYUU_GOGOKYUU_ARI,
        ]:
            days[1] += 0.5  # 出勤日数

        # 平日欠勤
        if result.status == WorkingStatus.C_KEKKIN:
            days[4] += 1  # 欠勤日数

        # 休日出社
        if result.status in [
            WorkingStatus.C_HOUTEI_KYUJITU,
            WorkingStatus.C_HOUTEIGAI_KYUJITU,
        ]:
            days[8] += 1  # 休日出勤日数
            days[1] += 1  # 出勤日数

        # 休日出社・半休
        if result.status in [
            WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
            WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_ARI,
            WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
            WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
        ]:
            days[8] += 0.5  # 休日出勤日数
            days[1] += 0.5  # 出勤日数

        # 有休
        if result.status in yuukyuu:
            if result.eval_code == WorkingStatus.C_YUUKYUU:
                days[2] += 1  # 有給
            else:
                days[2] += 0.5  # 有給
        # 代休
        if result.status in daikyuu:
            if result.eval_code == WorkingStatus.C_DAIKYUU:
                days[3] += 1  # 代休
            else:
                days[3] += 0.5  # 代休

        if result.status in tokubetukyuu:
            if result.status == WorkingStatus.C_TOKUBETUKYUU:
                days[5] += 1  # 特別球
            else:
                days[5] += 0.5  # 特別球

    # days[9] = 0
    return days


def accumulate_weekly_working_hours(attendances: list[Attendance]) -> list[tuple]:
    """週ごとの労働時間を累計する
    attendancesは１か月分の勤怠データを保持していること。足りないときはfill_missiing_attendanceで補うこと。

    :param attendances: 勤怠データのリスト
    :return: (n週, 週の始まり, 労働時間, 丸めた労働時間) * 週の数
    """

    if attendances is None:
        return []

    result: list[tuple] = []
    work_time = Const.TD_ZERO
    week = -1

    # とりあえず週の頭を設定する。入社したばかりの人は週の初めの日曜日のデータが存在しないので。
    week_begin = attendances[0].date
    for a in attendances:
        # 週の始まりは日曜日から
        if a.date.weekday() == 6:
            week_begin = a.date

        steppingout = tally_steppingout(a.employee, a.clock_in, a.clock_out)
        work_time += a.actual_work + steppingout

        # 土曜日は集計
        if a.date.weekday() == 5:
            week += 1
            result.append((week + 1, week_begin, work_time, floor_to_30min(work_time)))
            work_time = Const.TD_ZERO

    return result


def has_permitted_overtime_work(employee: Employee, date: datetime.date | None) -> bool:
    """employeeは残業が認められているか
    日毎の許可と固定残業制度の両方を考慮するので、通常はこの関数で判断すべき

    :param employee: Employee
    :param date: 日付
    :return: True:認められている False:認められていない
    """
    if employee.is_manager():
        # 管理職は常に残業が認められている
        return True
    if has_assigned_fixed_overtime_pay(employee):
        # みなし残業20時間が割り当てられている場合は常に残業が認められている
        return True

    if date is not None:
        if has_permitted_daily_overtime(employee, date):
            # 個別に残業が許可されている場合
            return True

    return False


def get_half_year_day(date: datetime.date) -> datetime.date:
    """半年前の日付を取得する"""
    dt = datetime.datetime.combine(date, datetime.time(0, 0, 0))
    return (dt + relativedelta(months=6)).date()


def get_annual_paied_holiday_days(date: datetime.date, join: datetime.date) -> float:
    """引数で渡された日の時点での年次休暇日数を取得する"""

    """                 0.5   1.5   2.5   3.5   4.5   5.5   6.5（年）"""
    num_holiday = [0.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0]

    if date < join:
        raise ValueError("date < join")
    s = join - relativedelta(months=6)  # 基準日を入社日の半年前にする
    for i in reversed(range(len(num_holiday))):
        if s + relativedelta(years=i) <= date:
            return num_holiday[i]

    return num_holiday[0]


def get_recent_day_of_annual_leave_update(
    year: int, join: datetime.date
) -> datetime.date:
    """年次有給休暇の更新日を取得する
    - 更新日は入社日の半年後になる
      それ以降は半年後の日付が更新日になる
    """

    return get_half_year_day(datetime.datetime(year, join.month, join.day))


def is_need_break_time(time: datetime.timedelta, code: int) -> bool:
    """
    休息が必要か(休息分勤務時間から引くか)

    - 6時間を*超えて*勤務したら休息が必要
    - 休日勤務でも６時間を超えたら休息が必要
    - 6時間ピッタリの場合は休息は不要
    - 午後休(休息あり)の場合は6時間以下でも休息が必要（半休扱い）

    """
    if time > Const.TD_6H:
        # 6時間を超えているので休息が必要
        return True
    if code in WorkingStatus.AFTERNOON_OFF_WITH_REST:
        # 午後休(休息あり)の場合は6時間以下でも休息が必要
        return True
    # それ以外の条件では休息は不要
    return False


def get_monthy_time_record(
    employee: Employee, date: datetime.date
) -> list[EmployeeDailyRecord]:
    """月で打刻を集めてlistにして返す
    もし打刻がない日はC_NONEのレコードを返す
    """
    # 集計
    days = enumrate_days(date)

    timerecords = []
    for day in days:
        try:
            record = EmployeeDailyRecord.objects.get(employee=employee, date=day)
        except EmployeeDailyRecord.DoesNotExist:
            record = EmployeeDailyRecord(
                employee=employee,
                date=day,
                status=WorkingStatus.C_NONE,
            )
        timerecords.append(record)
    return timerecords


def get_monthly_attendance(employee: Employee, date: datetime.date) -> list[Attendance]:
    """月次の勤怠データを取得する"""
    period = Period(
        datetime.datetime.combine(get_first_day(date), datetime.time(0, 0)),
        datetime.datetime.combine(get_last_day(date), datetime.time(0, 0)),
    )
    return get_attendance_in_period(employee, period)


def get_attendance_in_period(employee: Employee, period: Period) -> list[Attendance]:
    """指定された期間の勤怠データを取得する
    引数:
        employee    対象の社員
        start       期間の開始日
        end         期間の終了日（含む）
    戻り値:
        勤怠データのリスト
    """
    if period.start is None or period.end is None:
        raise ValueError("start or end is None")
    attendances = []
    for daily_record in DailyAttendanceRecord.objects.filter(
        time_record__employee=employee,
        time_record__date__gte=period.start.date(),
        time_record__date__lte=period.end.date(),
    ).order_by("time_record__date"):
        # attn_date = datetime.datetime.combine(
        #     daily_record.time_record.date, datetime.time(0, 0, 0)
        # )
        attn_date = daily_record.time_record.date
        attn = Attendance(date=attn_date, employee=employee, record=daily_record)
        attendances.append(attn)

    return attendances


def fill_missing_attendance(
    employee: Employee, period: Period, attendances: list[Attendance]
) -> list[Attendance]:
    """勤怠データの欠損を補う
    引数:
        employee    対象の社員
        attendances 取得した勤怠データのリスト
    戻り値:
        欠損を補った勤怠データのリスト
    """
    dates = [x.date for x in attendances]

    filled = []
    for d in period.range():
        d = d.date()
        if d not in dates:
            # まだ勤怠データが存在しない日があるので生成する
            attn = Attendance(date=d, employee=employee)
            filled.append(attn)
        else:
            filled.append(attendances[dates.index(d)])
    return filled


def get_employee_hour(employee: Employee, date: datetime.date) -> WorkingHour:
    """☑
    所定労働時間をデータベースから引っ張ってくる
    取得できないときはNoSpecifiedWorkingHoursError例外が発生する
    引数:employee
        date    この日付の「既定の勤務時間」を検索

    """
    for hour in EmployeeHour.objects.filter(employee=employee).order_by("-date"):
        if hour.date <= date:
            return hour.working_hours
    raise NoAssignedWorkingHourError(f"no specified working hour for {employee.name}")


def get_working_hour_pre_assign(employee: Employee) -> EmployeeHour:
    """☑
    事前割り当ての勤務時間を取得する(すでに適用されているかもしれないがこの関数では考慮しない)

    :param employee: 対象の社員
    :param date: この日付の「既定の勤務時間」を検索
    :return: WorkingHourオブジェクト
    """
    employee_hours = EmployeeHour.objects.filter(employee=employee).order_by("-date")
    if employee_hours:
        return employee_hours[0]
    raise ValueError("no specified working hour for %s" % employee.name)


def get_day_switch_time() -> datetime.time:
    """
    勤怠システムでの「日付変更時刻」を取得する
    ない
    """
    if not DaySwitchTime.objects.exists():
        # 存在しない場合はAM5:00に設定する
        DaySwitchTime.objects.create(switch_time=datetime.time(5, 0, 0))

    switch_time = DaySwitchTime.objects.first()
    if switch_time is None:
        return datetime.time(5, 0, 0)
    if switch_time.switch_time is None:
        return datetime.time(5, 0, 0)
    return switch_time.switch_time


def get_attendance_day() -> datetime.date:
    # 勤怠システムでは１日はAM5:00-翌AM4:59までとする
    # なので、もし日をまたいだAM0:00-AM4:59の間は前日の日付を返す
    now = datetime.datetime.now()
    return normalize_to_attendance_day(now).date()


def normalize_to_attendance_day(day: datetime.datetime) -> datetime.datetime:
    """日付を勤怠システムの日付に正規化する"""
    day_switch_time = get_day_switch_time()
    if day.time() < day_switch_time:
        # dayは日を跨いでる
        t = day.time()
        d = (day - datetime.timedelta(days=1)).date()
        day = datetime.datetime.combine(d, t)
    return day


def get_clock_in_out(stamps: Sequence[datetime.datetime]) -> Period:
    """打刻のリストから出社・退社のペアを取得する
    打刻がないときは(None, None)を返す
    打刻が1件のときは(打刻, None)を返す
    打刻が2件以上のときは(最初の打刻, 最後の打刻)を返す
    """
    if not stamps:
        return Period(None, None)
    if len(stamps) == 1:
        return Period(stamps[0], None)
    return Period(stamps[0], stamps[-1])


def generate_daily_record(
    stamps: Sequence[datetime.datetime], employee: Employee, date: datetime.date
) -> EmployeeDailyRecord | None:
    """EmployeeDailyRecordを生成する

        stampが空の時でもEmployDailyRecordを生成する
        もし勤務時間が設定されていないときは処理しない
    引数:
        stamps      打刻のリスト。空のときもあるし、1件のときもあるし、2件以上のときもある
        employee    対象の社員
        date        対象の日付
    """

    stamp = get_clock_in_out(stamps)

    try:
        employee_hours = get_employee_hour(employee, date).get_period(date)
        if calendar_is_holiday(date):
            # 休日の場合は所定の勤務時間は打刻と一致する
            employee_hours = stamp
    except NoAssignedWorkingHourError:
        # 勤務時間が設定されていないので処理しない
        logger.warning(f"勤務時間が設定されていません {employee.name} {date}")
        return
    except ValueError as e:
        logger.warning(f"勤務時間の取得に失敗しました {employee.name} {date} {e}")
        return
    working_status = determine_working_status(
        calendar_is_holiday(date), is_legal_holiday(date), not stamp.is_empty()
    )

    record = EmployeeDailyRecord(
        employee=employee,
        date=date,
        clock_in=stamp.start,
        clock_out=stamp.end,
        working_hours_start=employee_hours.start,
        working_hours_end=employee_hours.end,
        status=working_status,
    )
    record.save()
    return record


def adjust_stamp(
    stamp: Period, work_hours: Period, overtime_permission: bool
) -> Period:
    """打刻を調整する
    - 出社打刻が所定の勤務開始時間より前なら所定の勤務開始時間に調整する
    - 退社打刻が所定の勤務終了時間より後なら
      - 残業許可があるなら打刻のまま
      - 残業許可がないなら所定の勤務終了時間に調整する
    - stampはNoneでここに来ることがあるから、それを考慮すること
    """
    adjusted_stamp = Period(None, None)
    if stamp.start is not None and work_hours.start is not None:
        adjusted_stamp.start = adjust_work_start_time(stamp.start, work_hours.start)
    if stamp.end is not None and work_hours.end is not None:
        adjusted_stamp.end = adjust_work_end_time(
            stamp.end, work_hours.end, overtime_permission
        )
    return adjusted_stamp


def update_attendance_record_and_save(
    attendance: DailyAttendanceRecord,
) -> DailyAttendanceRecord:
    """勤怠データを更新する"""

    if attendance.clock_in is None or attendance.clock_out is None:
        return attendance
    if attendance.working_hours_start is None or attendance.working_hours_end is None:
        return attendance

    if attendance.date is None:
        return attendance
    if attendance.status is None:
        return attendance

    stamp = Period(attendance.clock_in, attendance.clock_out)
    if stamp.start is None or stamp.end is None:
        return attendance

    work_hours = Period(attendance.working_hours_start, attendance.working_hours_end)
    if work_hours.start is None or work_hours.end is None:
        return attendance

    # 外出時間
    # stepping_out = calc_stepping_out(attendance.employee, Period(begin_work, end_work))
    stepping_out = Const.TD_ZERO
    # 実労働時間(休息分は差し引かれてる)
    working_duration = calc_actual_working_hours(stamp, attendance.status, stepping_out)

    # 勤怠詳細を計算してセットする
    attendance.stepping_out = stepping_out
    attendance.actual_work = working_duration
    if calendar_is_holiday(attendance.date):
        if is_legal_holiday(attendance.date):
            attendance.legal_holiday = working_duration
        else:
            attendance.holiday = working_duration
    attendance.late = calc_tardiness(stamp.start, work_hours.start)
    attendance.early_leave = calc_leave_early(stamp.end, work_hours.end)
    attendance.over = calc_overtime(
        stamp.duration(),
        working_duration,
        has_permitted_overtime_work(attendance.employee, attendance.date),
    )

    attendance.over_8h = calc_over_8h(
        working_duration,
        has_permitted_overtime_work(attendance.employee, attendance.date),
    )
    # 休出でも深夜は計算する
    attendance.night = calc_midnight_work(stamp.end)
    attendance.save()
    return attendance


def initiate_daily_attendance_record(
    attendance: DailyAttendanceRecord,
) -> DailyAttendanceRecord:
    """勤怠データを初期化する

    :param attendance: DailyAttendanceRecord
    :return: 初期化されたDailyAttendanceRecord
    """

    if attendance.working_hours_start is None or attendance.working_hours_end is None:
        return attendance
    if attendance.date is None:
        return attendance
    if attendance.status is None:
        return attendance

    if has_permitted_overtime_work(attendance.employee, attendance.date):
        # 個別に残業が許可されている場合
        attendance.overtime_permitted = True

    if calendar_is_holiday(attendance.date) is True:
        # 休出の場合は打刻を調整しない
        # 休出所的勤務時間がないので打刻をそのまま勤務時間にする
        attendance.working_hours_start = attendance.clock_in
        attendance.working_hours_end = attendance.clock_out
        return attendance

    stamp = Period(attendance.clock_in, attendance.clock_out)
    work_hours = Period(attendance.working_hours_start, attendance.working_hours_end)
    stamp = adjust_stamp(stamp, work_hours, attendance.overtime_permitted)
    attendance.clock_in = stamp.start
    attendance.clock_out = stamp.end

    return attendance


def generate_attendance_record(record: EmployeeDailyRecord) -> DailyAttendanceRecord:
    """DailyAttendanceRecordを生成する
    :param record: EmployeeDailyRecord
    :return: 生成されたDailyAttendanceRecord"""

    if record is None:
        raise ValueError("record is None")
    if record.status is None:
        raise ValueError("record.status is None")

    attendance = DailyAttendanceRecord(
        time_record=record,
        employee=record.employee,
        date=record.date,
        clock_in=record.clock_in,
        clock_out=record.clock_out,
        working_hours_start=record.working_hours_start,
        working_hours_end=record.working_hours_end,
        status=record.status,
    )
    attendance.save()
    return attendance


def finalize_daily_record(employee: Employee, date: datetime.date):
    """EmployeeDailyRecordとDailyAttendanceRecordを生成する"""

    if EmployeeDailyRecord.objects.filter(employee=employee, date=date).exists():
        logger.info("[test]勤務記録が既に存在しているためスキップします")
        return

    # WebTimeStampを集める
    stamps = get_daily_webstamps(employee, date)

    # 勤務時間
    employee_hours = get_employee_hour(employee, date).get_period(date)

    # 外出打刻を抽出する
    stepouts = get_stepout_periods(stamps, employee_hours)

    try:
        with transaction.atomic():
            # EmployeeDailyRecordを生成する
            record = generate_daily_record(stamps, employee, date)
            if record is None:
                logger.info(f"[test]打刻データが存在しないためスキップします")
                return

            # recordからDailyAttendanceRecordを生成する
            attendance = generate_attendance_record(record)
            attendance = initiate_daily_attendance_record(attendance)
            update_attendance_record_and_save(attendance)

            # 外出のレコードを生成する
            generate_stepout_records(employee, stepouts)

    except Exception as e:
        logger.error(f"[test]レコードの生成に失敗しました: {employee} {date} {e}")
        return

    # 確認
    if not EmployeeDailyRecord.objects.filter(employee=employee, date=date).exists():
        logger.error(
            f"[test]EmployeeDailyRecordが生成されませんでした: {employee} {date}"
        )
        return
    else:
        logger.info("[test]EmployeeDailyRecordを生成しました")
    if not DailyAttendanceRecord.objects.filter(
        time_record__employee=employee, time_record__date=date
    ).exists():
        logger.error(f"DailyAttendanceRecordが生成されませんでした: {employee} {date}")
        return
    else:
        logger.info("[test]DailyAttendanceRecordを生成しました")

    # WebTimeStampを削除する
    remove_daily_webstamps(employee, date)

    return


# from django.db.models.query import QuerySet
# def collect_webstamps(employee: Employee, date: datetime.date) -> QuerySet:
#     """WebStampから日にちを指定してスタンプを収集"""
#     day_begin = datetime.datetime.combine(date, get_day_switch_time())
#     day_end = day_begin + datetime.timedelta(days=1)
#     stamps = WebTimeStamp.objects.filter(
#         employee=employee, stamp__gte=day_begin, stamp__lt=day_end
#     ).order_by("stamp")
#     return stamps


def get_daily_webstamps(
    employee: Employee, date: datetime.date
) -> list[datetime.datetime]:
    """WebStampから日にちを指定してスタンプを収集

    :param employee: 対象の社員
    :param date: 対象の日付
    :return: 打刻のリスト
    """
    day_begin = datetime.datetime.combine(date, get_day_switch_time())
    day_end = day_begin + datetime.timedelta(days=1)
    stamps = WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin, stamp__lt=day_end
    ).order_by("stamp")
    return [x.stamp for x in stamps if x.stamp is not None]


def remove_daily_webstamps(employee: Employee, date: datetime.date):
    """WebStampから日にちを指定してスタンプを削除

    :param employee: 対象の社員
    :param date: 対象の日付
    """
    day_begin = datetime.datetime.combine(date, get_day_switch_time())
    day_end = day_begin + datetime.timedelta(days=1)
    stamps = WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin, stamp__lt=day_end
    ).delete()


"""
    残業許可の管理
    
"""


def permit_daily_overtime(employee: Employee, date: datetime.date) -> None:
    """残業を許可する"""
    if has_permitted_daily_overtime(employee, date):
        # すでに許可されている
        logger.info(f"すでに残業が許可されています: {employee.name} {date}")
        return
    OvertimePermission.objects.update_or_create(employee=employee, date=date)
    logger.info(f"残業を許可しました: {employee.name} {date}")


def has_permitted_daily_overtime(employee: Employee, date: datetime.date) -> bool:
    """残業が許可されているかどうか"""
    return OvertimePermission.objects.filter(employee=employee, date=date).exists()


def revoke_daily_overtime_permission(employee: Employee, date: datetime.date) -> None:
    """残業許可を取り消す"""
    OvertimePermission.objects.filter(employee=employee, date=date).delete()
    logger.info(f"残業許可を取り消しました: {employee.name} {date}")


"""
    固定残業時間の設定
"""


def assign_fixed_overtime_pay(
    employee: Employee,
    hours: datetime.timedelta,
):
    """固定残業時間を設定する
    :param employee: 対象の社員
    :param hours: 固定残業時間
    """
    obj, created = FixedOvertimePayEmployee.objects.update_or_create(
        employee=employee, hours=hours
    )


def has_assigned_fixed_overtime_pay(employee: Employee) -> bool:
    """固定残業時間が設定されているかどうか"""
    return FixedOvertimePayEmployee.objects.filter(employee=employee).exists()


def remove_fixed_working_hours(employee: Employee, hours: datetime.timedelta) -> None:
    """固定残業時間の設定を削除する"""
    FixedOvertimePayEmployee.objects.filter(employee=employee, hours=hours).delete()


def assign_stamp_status(
    stamps: list[datetime.datetime], working_hours: Period
) -> list[tuple[datetime.datetime, int]]:
    """打刻にステータスを割り当てる
    - 打刻がない場合は空のリストを返す
    - 打刻が1件の場合は「出勤」
    - 打刻が2件以上の場合は、最初の打刻は「出勤」、最後の打刻は「退勤」
      それ以外の打刻は「外出」「戻り」を交互に割り当てる

    1 - 出勤
    2 - 外出
    3 - 戻り
    4 - 退勤


    """
    if working_hours.start is None or working_hours.end is None:
        return []

    status = []
    n = len(stamps)

    if n == 0:
        pass
    elif n == 1:
        if stamps[0] >= working_hours.end:
            status = [4]
        else:
            status = [1]
    else:
        status = [1]
        for i in range(1, n - 1):  # 出勤、退勤を除く
            status.append(2 if i % 2 == 1 else 3)

        if status[-1] == 2:  # 外出
            if stamps[-1] >= working_hours.end:
                status.append(4)
            else:
                status.append(3)  # 戻り
        else:  # 戻り
            status.append(4)  # 退勤

    stamps_with_status = []
    for i, label in enumerate(status):
        stamps_with_status.append((stamps[i], label))

    return stamps_with_status


def convert_status_to_display_string(
    stamps: list[tuple[datetime.datetime, int]],
) -> list[tuple[datetime.datetime, str]]:
    """打刻のステータスを表示用の文字列に変換する
    - 1 - 出勤
    - 2 - 外出
    - 3 - 戻り
    - 4 - 退勤
    """
    status_dict = {
        1: "出勤",
        2: "外出",
        3: "戻り",
        4: "退勤",
    }
    result = []
    for stamp, status in stamps:
        status_str = status_dict.get(status, "不明")
        result.append((stamp, status_str))
    return result


def get_stepout_periods(
    stamps: list[datetime.datetime],
    working_hours: Period,
) -> list[Period]:
    """打刻のリストから外出・戻りのペアを取得する
    - 外出がない場合は空のリストを返す
    - 外出が1件の場合はPeriod(stamp,None)を返す
    """
    stamps_with_status = assign_stamp_status(stamps, working_hours)
    periods = []

    for i in range(len(stamps_with_status) - 1):
        if stamps_with_status[i][1] == 2:
            if stamps_with_status[i + 1][1] == 3:
                periods.append(
                    Period(stamps_with_status[i][0], stamps_with_status[i + 1][0])
                )
            elif stamps_with_status[i + 1][1] == 4:
                periods.append(Period(stamps_with_status[i][0], None))
    return periods


def generate_stepout_records(employee: Employee, periods: list[Period]) -> None:
    """外出・戻りのペアからSteppingOutレコードを生成する"""
    for period in periods:
        so = SteppingOut(
            employee=employee,
            out_time=period.start,
            return_time=period.end,
        )
        so.save()
