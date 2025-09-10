import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from sao import models, core
from sao.attendance import Attendance
from sao.period import Period


def make_web_stamp_string(
    employee: models.Employee, date: datetime.date
) -> tuple[str, str]:
    """
    web打刻を文字列にして返す
    例: ("09:00", "18:00") or ("--:--:--", "--:--:--")

    :param employee: 雇用者
    :param date: 日付
    :return: (出勤時刻, 退勤時刻) どちらも--:--:--のときは打刻なし
    """
    fromTime = "--:--:--"
    toTime = "--:--:--"

    day_start = datetime.datetime.combine(date, core.get_day_switch_time())
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_start
    ).order_by("stamp")

    if stamps.count() == 0:
        return ("--:--:--", "--:--:--")
    first_stamp = stamps.first()
    last_stamp = stamps.last()
    if first_stamp is not None and first_stamp.stamp is not None:
        fromTime = first_stamp.stamp.strftime("%H:%M")
    if last_stamp is not None and last_stamp.stamp is not None:
        toTime = last_stamp.stamp.strftime("%H:%M")
        if fromTime == toTime:
            toTime = "--:--:--"
    return (fromTime, toTime)


def get_overtime_warning(overtime: datetime.timedelta) -> tuple:
    """見込み残業オーバーを警告する"""
    if overtime > datetime.timedelta(hours=25):
        return ("overtime_warn_25h", "25時間超")
    if overtime > datetime.timedelta(hours=23):
        return ("overtime_warn_23h", "23時間超")
    if overtime > datetime.timedelta(hours=20):
        return ("overtime_warn_20h", "20時間超")
    if overtime > datetime.timedelta(hours=15):
        return ("overtime_warn_15h", "15時間超")
    return ("", "")


def attention_overtime(overtime: datetime.timedelta) -> tuple:
    """超過勤務時間を注意喚起させる"""
    if overtime > datetime.timedelta(hours=100):
        return ("overtime_warn_100h", "100時間超")
    if overtime > datetime.timedelta(hours=60):
        return ("overtime_warn_60h", "60時間超")
    if overtime > datetime.timedelta(hours=40):
        return ("overtime_warn_40h", "40時間超")
    return get_overtime_warning(overtime)


def get_employee_type(type):
    """雇用形態コードを文字列にする"""
    name = ""
    if type == models.Employee.TYPE_PERMANENT_STAFF:
        name = "正社員"
    elif type == models.Employee.TYPE_TEMPORARY_STAFF:
        name = "派遣"
    else:
        name = "業務委託"
    return name


def get_department(type):
    """部署コードから文字列にする"""
    name = ""
    if type == models.Employee.DEPT_GENERAL:
        name = "一般"
    elif type == models.Employee.DEPT_DEVELOPMENT:
        name = "開発"
    return name


def create_user(username, last, first, password=None, email=None) -> User:
    """
    ユーザー作成
    """
    try:
        # すでにいた
        user = User.objects.get(username=username)
    except ObjectDoesNotExist:
        user = User.objects.create_user(
            username, email, password, last_name=last, first_name=first
        )
        if password:
            user.set_password(password)
        user.save()
    return user


def create_employee(**kwargs) -> models.Employee:
    """雇用者を作成する"""
    payed_holiday = kwargs["payed_holiday"] if "payed_holiday" in kwargs.keys() else 0.0
    leave_date = (
        kwargs["leave_date"]
        if "leave_date" in kwargs.keys()
        else datetime.date(2099, 12, 31)
    )
    include_overtime_pay = (
        kwargs["include_overtime_pay"]
        if "include_overtime_pay" in kwargs.keys()
        else False
    )
    employee = models.Employee(
        employee_no=kwargs["employee_no"],
        name=kwargs["name"],
        join_date=kwargs["join_date"],
        leave_date=leave_date,
        payed_holiday=payed_holiday,
        employee_type=kwargs["employee_type"],
        department=kwargs["department"],
        include_overtime_pay=include_overtime_pay,
        user=kwargs["user"],
    )
    employee.save()
    return employee


def get_employee_status(employee, date):
    """雇用者のステータスを文字列にする"""
    if employee.employee_type == models.Employee.TYPE_PERMANENT_STAFF:
        if employee.join_date > date:
            return "未入社"
        elif employee.leave_date < date:
            return "退社"
        else:
            return "在籍"
    else:
        if employee.join_date > date:
            return "未入社"
        elif employee.leave_date < date:
            return "契約終了"
        else:
            return "契約中"


def collect_webstamp(
    employee: models.Employee, date: datetime.date
) -> list[datetime.datetime]:
    """WebStampから日にちを指定してスタンプを収集"""
    day_begin = datetime.datetime.combine(date, core.get_day_switch_time())
    day_end = day_begin + datetime.timedelta(days=1)
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin, stamp__lt=day_end
    ).order_by("stamp")
    return [x.stamp for x in stamps if x.stamp is not None]


def print_strip_sec(total_sec, empty):
    """秒数をhh:mm形式にして返す"""
    h, m = divmod(total_sec // 60, 60)
    if h + m == 0:
        return empty
    h = int(h)
    m = int(m)

    m = f"0{m}"[-2:]  # 1桁の時は頭に0をつける
    return f"{h}:{m}"


def print_total_sec(total_sec):
    """秒数をhh:mm:ss形式にして返す"""
    total_sec = int(total_sec)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    s = f"0{s}"[-2:]  # 1桁の時は頭に0をつける
    m = f"0{m}"[-2:]  # 1桁の時は頭に0をつける
    return f"{h}:{m}:{s}"


def is_missed_stamp(clock_in, clock_out):
    """打刻漏れがあるかどうかを判定する"""
    if clock_in and clock_out:
        # どちらもある
        return False
    if not clock_in and not clock_out:
        # どちらもない
        return False

    return True


def is_empty_stamp(clock_in, clock_out):
    """打刻がないかどうかを判定する"""
    return True if (clock_in, clock_out) == (None, None) else False


def is_over_half_working_hours(
    target_time: datetime.datetime,
    employee: models.Employee,
    working_hours: tuple[datetime.datetime, datetime.datetime],
) -> bool:
    """所定労働時間の半分を超えているかどうか"""
    begin_time = working_hours[0]
    end_time = working_hours[1]
    duration = end_time - begin_time
    if target_time > begin_time + duration / 2:
        return True
    return False


# from ..models import EmployeeDailyRecord
# from ..attendance import Attendance
# def generate_attendance(record: EmployeeDailyRecord) -> Attendance:
#     return Attendance(record)


# def tally_monthly_attendance(month: int, records: list[EmployeeDailyRecord]) -> list[Attendance]:
#     """TimeRecordからAttendanceを作成する
#     month: 対象月
#     records: TimeRecordのリスト

#     employeeの所定労働時間が設定されていない場合はNoSpecifiedWorkingHoursErrorが発生する
#     """
#     result_record = []

#     summed_out_of_time = datetime.timedelta()
#     for r in records:
#         if r.date.month != month:
#             # 対象月の記録ではないので何もしない
#             continue
#         # 所定労働時間を取得
#         attendance = Attendance(r)
#         summed_out_of_time += attendance.over
#         attendance.summed_out_of_time = summed_out_of_time
#         result_record.append(attendance)
#     return result_record


def tally_over_work_time(
    month: int, attendances: list[Attendance]
) -> datetime.timedelta:
    """時間外勤務時間の合計を計算する
    month: 対象月
    records: 集計対象月の勤怠記録
    """
    over_work_time = datetime.timedelta()
    for attn in attendances:
        if attn.date.month != month:
            # 対象月の記録ではないので何もしない
            continue
        # 所定労働時間を取得
        over_work_time += attn.over
    return over_work_time


# def sumup_attendances(attendances: list[Attendance]) -> dict:
#     """
#     勤務評価結果の集計をする
#     引数       result CalculatedRecordの配列
#     """

#     summed_up = {
#         "work": datetime.timedelta(),
#         "late": datetime.timedelta(),
#         "before": datetime.timedelta(),
#         "steppingout": datetime.timedelta(),
#         "out_of_time": datetime.timedelta(),
#         "over_8h": datetime.timedelta(),
#         "night": datetime.timedelta(),
#         "legal_holiday": datetime.timedelta(),
#         "holiday": datetime.timedelta(),
#         "accumulated_overtime": datetime.timedelta(),
#     }
#     for attn in attendances:
#         if attn.work:
#             summed_up["work"] += attn.work
#             summed_up["late"] += attn.late
#             summed_up["before"] += attn.before
#             summed_up["steppingout"] += attn.steppingout
#             summed_up["out_of_time"] += attn.out_of_time
#             summed_up["over_8h"] += attn.over_8h
#             summed_up["night"] += attn.night
#             summed_up["legal_holiday"] += attn.legal_holiday
#             summed_up["holiday"] += attn.holiday

#             if not is_legal_holiday(attn.date):
#                 summed_up["accumulated_overtime"] += attn.out_of_time
#     return summed_up


def tally_attendances(attendances: list[Attendance]) -> dict:
    """
    勤務評価結果の集計をする
    引数       result CalculatedRecordの配列
    """

    summed_up = {
        "work": datetime.timedelta(),
        "late": datetime.timedelta(),
        "before": datetime.timedelta(),
        "steppingout": datetime.timedelta(),
        "out_of_time": datetime.timedelta(),
        "over_8h": datetime.timedelta(),
        "night": datetime.timedelta(),
        "legal_holiday": datetime.timedelta(),
        "holiday": datetime.timedelta(),
        "accumulated_overtime": datetime.timedelta(),
    }
    for attn in attendances:
        if attn.actual_work:
            summed_up["work"] += attn.actual_work
            summed_up["late"] += attn.late
            summed_up["before"] += attn.early_leave
            summed_up["steppingout"] += attn.stepping_out
            summed_up["out_of_time"] += attn.over
            summed_up["over_8h"] += attn.over_8h
            summed_up["night"] += attn.night
            summed_up["legal_holiday"] += attn.legal_holiday
            summed_up["holiday"] += attn.holiday

            if not is_legal_holiday(attn.date):
                summed_up["accumulated_overtime"] += attn.over
    return summed_up
