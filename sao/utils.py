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


def get_employee_type_display(type: int) -> str:
    """雇用形態を文字列にする

    :param type: 雇用形態コード
    :return: 雇用形態の文字列
    """
    name = ""
    if type == models.Employee.TYPE_PERMANENT_STAFF:
        name = "正社員"
    elif type == models.Employee.TYPE_TEMPORARY_STAFF:
        name = "派遣"
    else:
        name = "業務委託"
    return name


def get_department_display(type: int) -> str:
    """部署コードから文字列にする
    :param type: 部署コード
    :return: 部署の文字列
    """
    name = ""
    if type == models.Employee.DEPT_GENERAL:
        name = "一般"
    elif type == models.Employee.DEPT_DEVELOPMENT:
        name = "開発"
    return name


def create_user(username, last, first, password=None, email=None) -> User:
    """ユーザーを作成する

    :param username: ユーザー名
    :param last: 姓
    :param first: 名
    :param password: パスワード
    :param email: メールアドレス
    :return: Userオブジェクト
    すでに存在する場合はそれを返す
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
    """雇用者を作成する

    必須項目
    - employee_no
    - name
    - employee_type
    - department
    - user

    任意項目
    - join_date (デフォルト: 今日)
    - leave_date (デフォルト: 2099-12-31)
    - payed_holiday (デフォルト: 0.0)
    - include_overtime_pay (デフォルト: False)
    """
    if "employee_no" not in kwargs.keys():
        raise ValueError("employee_no is required")
    if "name" not in kwargs.keys():
        raise ValueError("name is required")
    if "employee_type" not in kwargs.keys():
        raise ValueError("employee_type is required")
    if "department" not in kwargs.keys():
        raise ValueError("department is required")
    if "user" not in kwargs.keys():
        raise ValueError("user is required")
    join_date = (
        kwargs["join_date"] if "join_date" in kwargs.keys() else datetime.date.today()
    )
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
        join_date=join_date,
        leave_date=leave_date,
        payed_holiday=payed_holiday,
        employee_type=kwargs["employee_type"],
        department=kwargs["department"],
        include_overtime_pay=include_overtime_pay,
        user=kwargs["user"],
    )
    employee.save()
    return employee


def get_employee_status_display(employee: models.Employee, date: datetime.date) -> str:
    """雇用者のステータスを文字列にする

    :param employee: 雇用者
    :param date: 判定日
    :return: ステータスの文字列"""
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


def format_seconds_to_hhmm(total_sec: int, empty: str) -> str:
    """秒数をhh:mm形式にして返す

    total_sec: 秒数
    empty: 0のときに返す文字列
    return: hh:mm形式の文字列
    """
    h, m = divmod(total_sec // 60, 60)
    if h + m == 0:
        return empty
    h = int(h)
    m = int(m)

    m = f"0{m}"[-2:]  # 1桁の時は頭に0をつける
    return f"{h}:{m}"


def format_seconds_to_hhmmss(total_sec: int) -> str:
    """秒数をhh:mm:ss形式にして返す

    total_sec: 秒数
    return: hh:mm:ss形式の文字列
    """
    total_sec = int(total_sec)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    s = f"0{s}"[-2:]  # 1桁の時は頭に0をつける
    m = f"0{m}"[-2:]  # 1桁の時は頭に0をつける
    return f"{h}:{m}:{s}"


def is_missed_stamp(clock_in: datetime.datetime, clock_out: datetime.datetime) -> bool:
    """打刻漏れがあるかどうかを判定する

    打刻漏れとは、出勤打刻または退勤打刻のどちらかがない場合
    どちらもある場合、どちらもない場合は打刻漏れではない
    """
    if clock_in and clock_out:
        # どちらもある
        return False
    if not clock_in and not clock_out:
        # どちらもない
        return False

    return True


def is_empty_stamp(clock_in: datetime.datetime, clock_out: datetime.datetime) -> bool:
    """打刻がないかどうかを判定する

    打刻がないとは、出勤打刻も退勤打刻もない場合
    """
    return True if (clock_in, clock_out) == (None, None) else False


def is_filled_stamp(clock_in: datetime.datetime, clock_out: datetime.datetime) -> bool:
    """打刻があるかどうかを判定する

    打刻があるとは、出勤打刻も退勤打刻もある場合
    """
    return not is_empty_stamp(clock_in, clock_out)


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
