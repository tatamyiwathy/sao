import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from .models import Employee, WebTimeStamp


def get_today_stamp(employee: Employee, date: datetime.date):
    """打刻を取得する"""
    fromTime = "--:--:--"
    toTime = "--:--:--"

    day_begin = datetime.datetime(date.year, date.month, date.day, 5, 0, 0)
    stamps = WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin
    ).order_by("stamp")

    if stamps.count() == 0:
        return ("--:--:--", "--:--:--")
    if stamps.first() is not None:
        fromTime = stamps.first().stamp.strftime("%H:%M")
    if stamps.last() is not None:
        toTime = stamps.last().stamp.strftime("%H:%M")
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
    if type == Employee.TYPE_PERMANENT_STAFF:
        name = "正社員"
    elif type == Employee.TYPE_TEMPORARY_STAFF:
        name = "派遣"
    else:
        name = "業務委託"
    return name


def get_department(type):
    """部署コードから文字列にする"""
    name = ""
    if type == Employee.DEPT_GENERAL:
        name = "一般"
    elif type == Employee.DEPT_DEVELOPMENT:
        name = "開発"
    return name


def create_user(username, last, first, password=None, email=None) -> User:
    """
    ユーザー作成
    """
    try:
        user = User.objects.get(username=username)
    except ObjectDoesNotExist:
        user = User.objects.create_user(
            username, email, password, last_name=last, first_name=first
        )
        user.save()
    return user


def create_employee(**kwargs) -> Employee:
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
    employee = Employee(
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
    if employee.employee_type == Employee.TYPE_PERMANENT_STAFF:
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


def collect_webstamp(employee_no: int, date: datetime.date):
    """WebStampから日にちを指定してスタンプを収集"""
    opening_hour = datetime.datetime(date.year, date.month, date.day, 5, 0, 0)
    closing_hour = opening_hour + datetime.timedelta(days=1)
    stamps = WebTimeStamp.objects.filter(
        employee=employee_no, stamp__gte=opening_hour, stamp__lt=closing_hour
    ).order_by("stamp")
    return stamps


def make_sesamo_form_stamp(employee: Employee, stamp: datetime.datetime):
    """セサモ形式の打刻データを生成する"""
    # 出退勤管理, 0-03-#-01-#, アクセス制御 , 打刻時刻, 000 区画外, 002 出退勤管理, カード番号, ユーザー, 雇用者番号
    return ['"出退勤管理"', "", "", '"%s"' % stamp, "", "", "", "", '"%d"' % employee]


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
        return False
    if not clock_in and not clock_out:
        return False

    return True


def is_empty_stamp(clock_in, clock_out):
    """打刻がないかどうかを判定する"""
    if clock_in:
        return False
    if clock_out:
        return False
    return True
