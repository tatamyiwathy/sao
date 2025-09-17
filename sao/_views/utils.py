import datetime
from django.contrib import messages as django_messages
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from django.shortcuts import render
from sao.exceptions import NoAssignedWorkingHourError
from sao.core import (
    get_employee_hour,
    get_working_hour_pre_assign,
    get_attendance_in_period,
    fill_missiing_attendance,
    round_attendance_summary,
    summarize_attendance_days,
)
from sao.models import Employee, WorkingHour
from sao.calendar import (
    get_first_day,
    get_last_day,
    get_next_month_date,
    get_last_month_date,
    is_holiday,
)
from sao.period import Period
from sao.utils import (
    tally_attendances,
    tally_over_work_time,
    attention_overtime,
    is_missed_stamp,
    is_empty_stamp,
)
from sao.attendance import Attendance
from sao.const import Const


def get_employee_hours_display(employee: Employee) -> WorkingHour | None:
    """設定された勤務時間を取得する

    :param employee: Employeeオブジェクト
    :return: WorkingHourオブジェクト、勤務時間が設定されていない場合はNone
    """
    try:
        return get_employee_hour(employee, datetime.date.today())
    except NoAssignedWorkingHourError:
        # 合流前で勤務時間が取得できない
        try:
            return get_working_hour_pre_assign(employee).working_hours
        except ValueError:
            return None


def get_employee_by_user(user: User) -> Employee | None:
    try:
        return Employee.objects.get(user=user)
    except ObjectDoesNotExist:
        return None


def get_attendance_warnings(attn: Attendance, display_day: datetime.date) -> dict:
    """警告メッセージを作成する"""
    warnings = {}
    if attn.remark:
        # 処理済み
        return {}

    if (display_day - attn.date.date()).days < 2:
        # 猶予期間
        return {}

    if is_missed_stamp(attn.clock_in, attn.clock_out):
        # 打刻が片方だけ
        warnings["missed_stamp"] = "打刻を忘れていませんか？"
    if not is_holiday(attn.date.date()) and is_empty_stamp(
        attn.clock_in, attn.clock_out
    ):
        # 平日で打刻なし
        warnings["nostamp_workday"] = "欠勤の届を提出していますか？"
    if attn.legal_holiday > Const.TD_ZERO:
        # 法定休日で打刻あり
        warnings["legal_holiday"] = "休日出勤の届を提出していますか？"
    if attn.holiday > Const.TD_ZERO:
        # 休日で打刻あり
        warnings["holiday"] = "休日出勤の届を提出していますか？"
    if attn.late > Const.TD_ZERO:
        # 遅刻
        warnings["tardy"] = "遅刻の届を提出していますか？"
    if attn.early_leave > Const.TD_ZERO:
        # 早退
        warnings["leave_early"] = "早退の届を提出していますか？"
    if attn.night > Const.TD_ZERO:

        # 深夜
        warnings["midnight_work"] = "深夜勤務の申請を提出していますか？"

    # if attn.stepping_out > Const.TD_ZERO:
    #     # 外出
    #     warnings["steppingout"] = "外出があります"

    return warnings


def is_need_overwork_notification(attn: Attendance, display_day: datetime.date) -> bool:
    """残業の通知が必要かどうかを判定する"""
    if attn.total_overtime <= Const.OVERTIME_WORK_WARNING:
        return False

    if attn.remark:
        # 処理済み
        return False

    if (display_day - attn.date).days < 2:
        # 猶予期間
        return False

    if is_holiday(attn.date) and is_empty_stamp(attn.clock_in, attn.clock_out):
        return False

    return True


def collect_attendance_warning_messages(
    attendances: list[Attendance],
    display_date: datetime.date,
    today: datetime.date,
) -> list[str]:
    """警告メッセージを設定する"""
    messages = []
    for attn in attendances:
        warnings = get_attendance_warnings(attn, today)
        if warnings:
            attn.warnings = warnings
            # messages.append(
            #     "%d/%d 届出の提出がされていない可能性があります。勤務データをご確認の上、届出の提出を行ってください"
            #     % (attn.date.month, attn.date.day),
            # )

        if is_need_overwork_notification(attn, today):
            messages.append(
                "%d/%d 残業が25時間を越えました。速やかに管理者へ届け出を行ってください。"
                % (attn.date.month, attn.date.day),
            )

    if (
        is_need_overwork_notification(attn, today)
        and (attendances[-1].total_overtime <= Const.OVERTIME_WORK_WARNING)
        and (attendances[-1].total_overtime > Const.OVERTIME_WORK_PRE_WARNING)
    ):
        if display_date.year == today.year and display_date.month == today.month:
            messages.append(
                "残業時間が25時間を越えそうです。25時間を越えないようにするか、超過手続きを管理者に届け出る準備をお願いします。",
            )

    return messages


def collect_display_attendances(
    employee: Employee, view_date: datetime.date
) -> list[Attendance]:
    """表示する勤怠データを取得する
    :param employee: Employeeオブジェクト
    :param view_date: 表示する年月日
    :return: Attendanceオブジェクトのリスト"""
    first_day = datetime.datetime.combine(get_first_day(view_date), datetime.time(0, 0))
    next_month_first_day = datetime.datetime.combine(
        get_last_day(view_date) + datetime.timedelta(days=1), datetime.time(0, 0)
    )
    period = Period(first_day, next_month_first_day)
    # 月次集計
    attendances = get_attendance_in_period(employee, period)
    # 欠損日補完
    attendances = fill_missiing_attendance(employee, period, attendances)
    return attendances


def render_employee_attendance(
    attendances: list[Attendance],
    view_date: datetime.date,
) -> dict:

    render_args = {}
    # 時間外労働時間を集計する
    attendances[-1].total_overtime = tally_over_work_time(view_date.month, attendances)
    # 集計する
    tallied_attn = tally_attendances(attendances)
    render_args["total_result"] = tallied_attn

    # 時間外勤務についての警告
    warn_class, warn_title = attention_overtime(tallied_attn["out_of_time"])
    render_args["warn"] = warn_class

    # 計算結果をまるめる
    render_args["rounded"] = round_attendance_summary(tallied_attn)
    render_args["days_counted"] = summarize_attendance_days(attendances, view_date)

    return render_args
