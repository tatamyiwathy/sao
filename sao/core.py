import datetime

import sao.calendar
import logging

from .models import (
    EmployeeDailyRecord,
    Employee,
    SteppingOut,
    EmployeeHour,
    WorkingHour,
    DaySwitchTime,
    DailyAttendanceRecord,    
)
from .working_status import WorkingStatus
from .const import Const
from .calendar import is_holiday, is_legal_holiday
from .period import Period
from .working_status import get_working_status
from dateutil.relativedelta import relativedelta


logger = logging.getLogger("sao")


def get_adjusted_working_hours(status: int, working_hour: Period) -> Period:

    """午前休、午後休に応じて所定の勤務時間を調整する"""

    if working_hour.is_empty():
        raise ValueError("勤務時間の設定がありません")
    
    start = working_hour.start
    end = working_hour.end
    duration = end - start

    if duration > Const.TD_6H:
        duration -= Const.TD_1H

    if status in WorkingStatus.MORNING_OFF:
        # 午前休なので開始時間を 所定労働時間の半分と休息１時間分ずらす
        start = start + duration / 2 + Const.TD_1H
    if status in WorkingStatus.AFTERNOON_OFF_WITH_REST:
        end = end - duration / 2
    elif status in WorkingStatus.AFTERNOON_OFF_NO_REST:
        # 休息なしなので休息１時間分ずらす
        end = end - duration / 2 - Const.TD_1H
    return Period(start, end)

def adjust_working_hours(record: EmployeeDailyRecord) -> Period:
    """勤務の開始、終了時間を調整する"""
    if is_holiday(record.date):
        # 休日出勤はそのまま返す
        return record.get_clock_in_out()
    
    working_hours = record.get_scheduled_time()
    if working_hours.is_empty():
        raise ValueError(f"平日なのに勤務時間の設定がありません {record.employee.name} {record.date}")
    
    return get_adjusted_working_hours(record.status, record.get_scheduled_time())

# def adjust_working_hours(record: EmployeeDailyRecord) -> tuple:
#     """勤務の開始、終了時間を調整する

#     ・勤務の開始時刻と終了時刻をtupleで返す
#     ・通常は所定の開始/終了時間を返す
#     ・休日出勤はそのまま返す
#     ・午前休/午後休の場合はそれぞれ調整して返す
#     ・所定の勤務時間が６時間を超えるなら終了時間を休息時間分前倒しする
#     ・Employeeに勤務時間の設定がないとNoSpecifiedWorkingHoursError例外が発生する
#     """

#     def adjust_scheduled_time(status: WorkingStatus, scheduled: tuple) -> tuple:
#         """午前休、午後休に応じて所定の勤務時間を調整する"""
#         begin_work_time = scheduled[0]
#         end_work_time = scheduled[1]
#         if status:
#             duration = end_work_time - begin_work_time
#             if duration > Const.TD_6H:
#                 duration -= Const.TD_1H
#             if status in WorkingStatus.MORNING_OFF:
#                 # 午前休なので開始時間を 所定労働時間の半分と休息１時間分ずらす
#                 begin_work_time = scheduled[0] + duration / 2 + Const.TD_1H
#             if status in WorkingStatus.AFTERNOON_OFF_WITH_REST:
#                 end_work_time = scheduled[1] - duration / 2
#             elif status in WorkingStatus.AFTERNOON_OFF_NO_REST:
#                 # 休息なしなので休息１時間分ずらす
#                 end_work_time = scheduled[1] - duration / 2 - Const.TD_1H
#         return (begin_work_time, end_work_time)

#     if is_holiday(record.date):
#         # 休日出勤はそのまま返す
#         clockin = record.get_clock_in()
#         clockout = record.get_clock_out()
#         return (clockin, clockout)

#     working_hour = get_employee_hour(record.employee, record.date)
#     return adjust_scheduled_time(
#         record.status,
#         (
#             datetime.datetime.combine(record.date, working_hour.begin_time),
#             datetime.datetime.combine(record.date, working_hour.end_time),
#         ),
#     )


def calc_assumed_working_time(
    record: EmployeeDailyRecord, begin_work: datetime.datetime|None, end_work: datetime.datetime|None
) -> datetime.timedelta:
    """想定されている実労働時間を計算する
    ・労働時間が６時間を超えるなら休息時間分が１時間引かれる
    ・休日の場合は休息時間は引かれない
    """
    if None in [begin_work, end_work]:
        return Const.TD_ZERO

    period = end_work - begin_work
    if is_need_break_time(period, record.status):
        period -= Const.TD_1H
    return period


class NoAssignedWorkingHourError(Exception):
    def __init__(self, arg=""):
        self.arg = arg

    def __str__(self):
        return self.arg


def round_down(t: datetime.timedelta) -> datetime.timedelta:
    """30分単位で切り下げ"""
    return datetime.timedelta(seconds=t.total_seconds() // 1800 * 1800)


def round_stamp(t: datetime.timedelta) -> datetime.timedelta:
    """30分未満は切り捨て、以上は切り上げ"""
    if t.seconds % 3600 < 1800:
        return round_down(t)
    return datetime.timedelta(seconds=(t.total_seconds() // 3600 + 1) * 3600)


def round_result(result: dict) -> dict:
    """
    まるめる
    """

    rounded = {}
    rounded["work"] = round_down(result["work"])
    rounded["late"] = round_down(result["late"])
    rounded["before"] = round_down(result["before"])
    rounded["steppingout"] = round_down(result["steppingout"])
    rounded["accumulated_overtime"] = round_down(result["accumulated_overtime"])

    # 時外勤、深夜、法定、所定は３０分未満切り下げ、３０分以上切り上げ       14/02/13
    rounded["out_of_time"] = round_stamp(result["out_of_time"])
    rounded["night"] = round_stamp(result["night"])
    rounded["legal_holiday"] = round_stamp(result["legal_holiday"])
    rounded["holiday"] = round_stamp(result["holiday"])
    # 151225 割増も切捨てではない
    rounded["over_8h"] = round_stamp(result["over_8h"])

    return rounded


def get_adjusted_starting_time(
    record: EmployeeDailyRecord, starting_time: datetime.datetime
) -> datetime.datetime:
    """
    業務を開始した時間を取得する

    遅刻してなければ所定の開始時間を返す
    そうでないなら遅刻した時間を返す
    """
    clock_in = record.get_clock_in()
    if clock_in is None:
        raise ValueError("clock_inがNone")

    if (clock_in - starting_time).days < 0:
        return starting_time

    # 遅刻してるので打刻時間をそのまま返す
    return clock_in


def get_adjusted_closing_time(
    record: EmployeeDailyRecord, closing_time: datetime.datetime, overtime_permittion: bool
) -> datetime.datetime:
    """
    業務を終了した時間を取得する

    終業の打刻が所定の就業時間を超過しているとき、
    残業申請があればそのまま打刻時間が終業時刻になる
    マネージャは上記の制約を受けない
    """

    clock_out = record.get_clock_out()
    if clock_out is None:
        raise ValueError("clock_outがNone")
    if (clock_out - closing_time).days < 0:
        # 早退
        return clock_out
    if overtime_permittion:
        # 残業OK
        return clock_out
    # 所定終業時間
    return closing_time


def calc_actual_working_time(
    record: EmployeeDailyRecord,
    begin_work: datetime.datetime|None,
    end_work: datetime.datetime|None,
    steppingout: datetime.timedelta,
) -> datetime.timedelta:
    """
    実際の労働時間を計算する
    ・休息時間は含まれていない
    ・遅刻の場合は出社打刻が調整される
    ・早退の場合は退社打刻が調整される
    """

    if record.get_clock_in() is None:
        return Const.TD_ZERO
    if record.get_clock_out() is None:
        return Const.TD_ZERO
    if record.status in WorkingStatus.NO_ACTUAL_WORK:
        return Const.TD_ZERO

    st = get_adjusted_starting_time(record, begin_work)
    ct = get_adjusted_closing_time(
        record,
        end_work,
        is_permit_overtime(record.employee) or record.is_overtime_work_permitted,
    )
    t = ct - st
    if t < Const.TD_ZERO:
        return Const.TD_ZERO
    # 休息が櫃量なら１時間差し引く
    if is_need_break_time(t, record.status):
        t -= Const.TD_1H

    # 外出を差し引く
    return t - steppingout


def calc_tardiness(
    record: EmployeeDailyRecord, start_time: datetime.datetime
) -> datetime.timedelta:
    """遅刻時間の計算

    """
    if record.get_clock_in() is None:
        return Const.TD_ZERO
    if record.is_holidaywork():
        return Const.TD_ZERO
    if record.status in WorkingStatus.NO_ACTUAL_WORK:
        return Const.TD_ZERO
    clock_in = record.get_clock_in()

    d = clock_in - start_time
    return d if d.days >= 0 else Const.TD_ZERO


def calc_leave_early(
    record: EmployeeDailyRecord, close_time: datetime.datetime
) -> datetime.timedelta:
    """
    早退時間の計算
    もし退勤の打刻がない場合は早退もないこととする
    （その場合は不整合が発生するはず）
    """
    clock_out = record.get_clock_out()
    if clock_out is None:
        # 退勤の打刻がない
        return Const.TD_ZERO
    if record.is_holidaywork():
        # 休日なので早退も発生しない
        return Const.TD_ZERO
    if close_time < clock_out:
        # 早退ではない
        return Const.TD_ZERO
    if record.status in WorkingStatus.NO_ACTUAL_WORK:
        # 欠勤してる
        return Const.TD_ZERO
    return close_time - clock_out


def tally_steppingout(timerecord: EmployeeDailyRecord) -> datetime.timedelta:
    """
    外出時間を集計する
    もし出勤/退勤の打刻がないばあいは0を返す
    """
    clock_in = timerecord.get_clock_in()
    if clock_in is None:
        return Const.TD_ZERO
    clock_out = timerecord.get_clock_out()
    if clock_out is None:
        return Const.TD_ZERO

    total_steppingout = Const.TD_ZERO
    for steppingout in SteppingOut.objects.filter(
        employee=timerecord.employee,
        out_time__gte=clock_in,
        return_time__lt=clock_out,
    ):
        if steppingout.out_time is None or steppingout.return_time is None:
            continue
        total_steppingout += steppingout.return_time - steppingout.out_time
    return total_steppingout


def calc_overtime(
    record: EmployeeDailyRecord,
    actual_work: datetime.timedelta,
    scheduled_working_period: datetime.timedelta,
) -> datetime.timedelta:
    """時間外勤務の時間を計算する

    実打刻と終業予定時刻の差分
    """
    if record.is_holidaywork():
        return Const.TD_ZERO
    if record.status in WorkingStatus.NO_ACTUAL_WORK:
        return Const.TD_ZERO
    if record.get_clock_out() is None:
        return Const.TD_ZERO
    if (
        not is_permit_overtime(record.employee)
        and not record.is_overtime_work_permitted
    ):
        return Const.TD_ZERO

    overtime = Const.TD_ZERO
    if actual_work > scheduled_working_period:
        overtime = actual_work - scheduled_working_period
    return overtime


def calc_over_8h(
    record: EmployeeDailyRecord, actual_work: datetime.timedelta
) -> datetime.timedelta:
    """
    勤務時間が8時間を超過した時間を計算する
    ８時間を超えた分は割増料金になる
    ・休日出勤の場合はそちらで割増の計算があるのでここでは計算しない
    """
    if record.is_holidaywork():
        return Const.TD_ZERO
    if record.status in WorkingStatus.NO_ACTUAL_WORK:
        return Const.TD_ZERO
    d = actual_work - Const.TD_8H
    return d if d.days >= 0 else Const.TD_ZERO


def calc_midnight_work(timerecord: EmployeeDailyRecord) -> datetime.timedelta:
    """
    深夜超過時間 深夜=22:00~
    """
    clock_out = timerecord.get_clock_out()
    if clock_out is None:
        raise ValueError("clock_outがNone")
    night = datetime.datetime.combine(timerecord.date, Const.NIGHT_WORK_START)
    d = clock_out - night
    return d if d.days >= 0 else Const.TD_ZERO


def calc_legal_holiday(
    timerecord: EmployeeDailyRecord, actual_work: datetime.timedelta
) -> datetime.timedelta:
    """休出(法定)ならそのまま返す"""
    if timerecord.date.weekday() == 6:  # 日曜日
        return actual_work
    return Const.TD_ZERO


def calc_holiday(
    timerecord: EmployeeDailyRecord, actual_work: datetime.timedelta
) -> datetime.timedelta:
    """休出(法定外)ならそのまま返す"""
    if is_holiday(timerecord.date):
        if not is_legal_holiday(timerecord.date):
            return actual_work
    return Const.TD_ZERO


def count_days(results: list, year_month: datetime.date) -> list:
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

    days[0] = sao.calendar.count_working_days(year_month)  # 所定勤務日数

    for result in results:
        if result.late:
            days[6] += 1  # 遅刻回数

        if result.before:
            days[7] += 1  # 早退回数

        # 平日出社
        if result.eval_code == WorkingStatus.C_KINMU:
            days[1] += 1  # 出勤日数

        # 平日出社・半休
        if result.eval_code in [
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
        if result.eval_code == WorkingStatus.C_KEKKIN:
            days[4] += 1  # 欠勤日数

        # 休日出社
        if result.eval_code in [
            WorkingStatus.C_HOUTEI_KYUJITU,
            WorkingStatus.C_HOUTEIGAI_KYUJITU,
        ]:
            days[8] += 1  # 休日出勤日数
            days[1] += 1  # 出勤日数

        # 休日出社・半休
        if result.eval_code in [
            WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
            WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_ARI,
            WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
            WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
        ]:
            days[8] += 0.5  # 休日出勤日数
            days[1] += 0.5  # 出勤日数

        # 有休
        if result.eval_code in yuukyuu:
            if result.eval_code == WorkingStatus.C_YUUKYUU:
                days[2] += 1  # 有給
            else:
                days[2] += 0.5  # 有給
        # 代休
        if result.eval_code in daikyuu:
            if result.eval_code == WorkingStatus.C_DAIKYUU:
                days[3] += 1  # 代休
            else:
                days[3] += 0.5  # 代休

        if result.eval_code in tokubetukyuu:
            if result.eval_code == WorkingStatus.C_TOKUBETUKYUU:
                days[5] += 1  # 特別球
            else:
                days[5] += 0.5  # 特別球

    # days[9] = 0
    return days


def accumulate_weekly_working_hours(records: list[EmployeeDailyRecord]) -> list[tuple]:
    """週ごとの労働時間を累計する

    戻り    (n週, 週の始まり, 労働時間, 丸めた労働時間) * 週の数
    """

    if records is None:
        return []
    if len(records) == 0:
        return []

    result: list[tuple] = []
    work_time = Const.TD_ZERO
    week = -1

    # とりあえず週の頭を設定する。入社したばかりの人は週の初めの日曜日のデータが存在しないので。
    week_begin = records[0].date
    for r in records:
        # 週の始まりは日曜日から
        if r.date.weekday() == 6:
            week_begin = r.date

        # 所定の始業、終業、勤務時間を取得する
        working_hours = adjust_working_hours(r)

        # 実労働時間
        steppingout = tally_steppingout(r)
        work_time += calc_actual_working_time(r, working_hours.start, working_hours.end, steppingout)

        # 土曜日は集計
        if r.date.weekday() == 5:
            week += 1
            result.append((week + 1, week_begin, work_time, round_down(work_time)))
            work_time = Const.TD_ZERO

    return result


def is_permit_overtime(employee: Employee) -> bool:
    """
    employeeは残業が認められているか
    """
    return employee.include_overtime_pay or employee.is_manager()


def get_half_year_day(date: datetime.datetime) -> datetime.datetime:
    """半年前の日付を取得する"""
    return date + relativedelta(months=6)


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
    """指定した都市の年次有給休暇の更新日を取得する
    更新日は入社日の半年後になる
    それ以降は半年後の日付が更新日になる
    """

    return get_half_year_day(datetime.datetime(year, join.month, join.day)).date()


def is_need_break_time(time: datetime.timedelta, code: WorkingStatus) -> bool:
    """
    休息が必要か

    6時間を*超えて*勤務したら1時間休息
    休日勤務でも６時間を超えたら休息が必要

    6時間ピッタリの場合は休息は不要
    """
    if code in WorkingStatus.HOLIDAY:
        return False

    if time > Const.TD_6H:
        return True

    if code in WorkingStatus.AFTERNOON_OFF_WITH_REST:
        return True

    # それ以外の条件では休息は不要？
    return False


def collect_timerecord_by_month(employee: Employee, date: datetime.date) -> list:
    """月で打刻を集めてlistにして返す
    もし打刻がない日はC_NONEのレコードを返す
    """
    # 集計
    days = sao.calendar.enumlate_days(date)

    timerecords = []
    for day in days:
        records = EmployeeDailyRecord.objects.filter(employee=employee).filter(date=day)
        if records.count() > 0:
            for record in records:
                timerecords.append(record)
        else:
            working_hours = get_employee_hour(employee, day)
            timerecords.append(
                EmployeeDailyRecord(employee=employee, date=day, 
                                    working_hours_start=datetime.datetime.combine(day, working_hours.begin_time),
                                    working_hours_end=datetime.datetime.combine(day, working_hours.end_time),
                                    status=WorkingStatus.C_NONE)
            )
    return timerecords


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


def get_working_hours_by_category(category: str) -> WorkingHour:
    """☑引数に渡されたカテゴリー名の勤務時間を取得する"""
    return WorkingHour.objects.get(category=category)


def get_working_hours_tobe_assign(employee: Employee) -> EmployeeHour:
    """☑
    適用予定の勤務時間を取得する(すでに適用されているかもしれないがこの関数では考慮しない)
    引数:     employee
            date    この日付の「既定の勤務時間」を検索
    戻り値     WorkingHourオブジェクト
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

def get_today() -> datetime.date:
    # 勤怠システムでは１日はAM5:00-翌AM4:59までとする
    # なので、もし日をまたいだAM0:00-AM4:59の間は前日の日付を返す
    now = datetime.datetime.now()
    return normalize_to_business_day(now).date()

def normalize_to_business_day(day: datetime.datetime) -> datetime.datetime:
    """日付をビジネスデーに正規化する"""
    day_switch_time = get_day_switch_time()
    if day.time() < day_switch_time:
        # dayは日を跨いでる
        t = day.time()
        d = (day - datetime.timedelta(days=1)).date()
        day = datetime.datetime.combine(d, t)
    return day


def get_clock_in_out(stamps: list[datetime.datetime]) -> Period:
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


def generate_daily_record(stamps: list[datetime.datetime], employee: Employee, date: datetime.date):
    """EmployeeDailyRecordを生成する
    引数:
        stamps      打刻のリスト。空のときもあるし、1件のときもあるし、2件以上のときもある
        employee    対象の社員
        date        対象の日付
    """

    clock_in_out = get_clock_in_out(stamps)

    try:
        working_hour = get_employee_hour(employee, date)
        scheduled_time = working_hour.get_paired_time(date)
        if is_holiday(date):
            # 休日の場合は所定の勤務時間は設定しない
            scheduled_time = Period(None, None)
    except NoAssignedWorkingHourError:
        # 勤務時間が設定されていないので処理しない
        return

    working_status = get_working_status(is_holiday(date), is_legal_holiday(date), not clock_in_out.is_empty())

    EmployeeDailyRecord(
        employee=employee,
        date=date,
        clock_in=clock_in_out.start,
        clock_out=clock_in_out.end,
        working_hours_start = scheduled_time.start,
        working_hours_end = scheduled_time.end,
        status=working_status,
    ).save()


def generate_attendance_record(record: EmployeeDailyRecord):
    """DailyAttendanceRecordを生成する"""
    attendance = DailyAttendanceRecord(time_record=record)
        
    # 所定の始業、終業、勤務時間を取得する
    begin_work = record.clock_in
    end_work = record.clock_out
    
    # 調整された出勤時間、退勤時間
    working_hours = adjust_working_hours(record)

    # 予定勤務時間
    assumed_working_time = calc_assumed_working_time(record, working_hours.start, working_hours.end)

    # 実労働時間(休息分は差し引かれてる)
    actual_working_time = calc_actual_working_time(record, working_hours.start, working_hours.end, Const.TD_ZERO)

    attendance.actual_working_time = actual_working_time
    attendance.late_time = calc_tardiness(record, working_hours.start)
    attendance.early_leave = calc_leave_early(record, working_hours.end)
    attendance.over_time = calc_overtime(record, actual_working_time, assumed_working_time)
    if attendance.over_time is not None and attendance.over_time.total_seconds() > 0:
        attendance.over_8h = calc_over_8h(record, actual_working_time)
        attendance.night_work = calc_midnight_work(record)
    attendance.legal_holiday_work = calc_legal_holiday(record, actual_working_time)
    attendance.holiday_work = calc_holiday(record, actual_working_time)
    attendance.status = record.status
    attendance.save()
