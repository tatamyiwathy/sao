import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from . import models, working_status, core, const

def get_today_stamp(employee: models.Employee, date: datetime.date):
    """打刻を取得する"""
    fromTime = "--:--:--"
    toTime = "--:--:--"

    day_begin = datetime.datetime.combine(date, core.get_day_switch_time())
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin
    ).order_by("stamp")

    if stamps.count() == 0:
        return ("--:--:--", "--:--:--")
    first_stamp = stamps.first()
    last_stamp = stamps.last()
    if first_stamp is not None and getattr(first_stamp, 'stamp', None) is not None:
        if first_stamp.stamp is not None:
            fromTime = first_stamp.stamp.strftime("%H:%M")
    if last_stamp is not None and getattr(last_stamp, 'stamp', None) is not None:
        if last_stamp.stamp is not None:
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


def collect_webstamp(employee: models.Employee, date: datetime.date) -> list[datetime.datetime]:
    """WebStampから日にちを指定してスタンプを収集"""
    day_begin = datetime.datetime.combine(date, core.get_day_switch_time())
    day_end = day_begin + datetime.timedelta(days=1)
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin, stamp__lt=day_end
    ).order_by("stamp")
    return [ x.stamp for x in stamps if x.stamp is not None ]

from django.db.models.query import QuerySet
def collect_webstamps(employee: models.Employee, date: datetime.date) -> QuerySet:
    """WebStampから日にちを指定してスタンプを収集"""
    day_begin = datetime.datetime.combine(date, core.get_day_switch_time())
    day_end = day_begin + datetime.timedelta(days=1)
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=day_begin, stamp__lt=day_end
    ).order_by("stamp")
    return stamps


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


def is_over_half_working_hours(target_time: datetime.datetime,
        employee: models.Employee, working_hours: tuple[datetime.datetime, datetime.datetime]) -> bool:
    
    """所定労働時間の半分を超えているかどうか"""
    begin_time = working_hours[0]
    end_time = working_hours[1]
    duration = end_time - begin_time
    if target_time > begin_time + duration / 2:
        return True
    return False


def generate_daily_record(stamps: list[datetime.datetime], employee: models.Employee, date: datetime.date):
    """EmployeeDailyRecordを生成する"""

    try:
        working_hour =core.get_employee_hour(employee, date)
        scheduled_start_time = datetime.datetime.combine(date, working_hour.begin_time)
        scheduled_end_time = datetime.datetime.combine(date, working_hour.end_time)
    except core.NoAssignedWorkingHourError:
        # 勤務時間が設定されていないので処理しない
        return

    context = {
        "employee": employee,
        "date": date,
    }
    if not stamps:
        # 打刻がないので空のEmployeeDailyRecordを生成する
        context["clock_in"] = None
        context["clock_out"] = None
        if core.is_holiday(date):
            context["scheduled_start_time"] = None
            context["scheduled_end_time"] = None
            context["status"] = working_status.WorkingStatus.C_KYUJITU
        else:
            context["scheduled_start_time"] = scheduled_start_time
            context["scheduled_end_time"] = scheduled_end_time
            context["status"] = working_status.WorkingStatus.C_KEKKIN
    elif len(stamps) == 1:
        # 打刻が1件しかないので、出社のみ登録する
        stamp = stamps[0]
        if core.is_holiday(date):
            # 休日は出社打刻がある場合は出勤・退勤ともに登録する
            context["clock_in"] = stamp
            context["clock_out"] = stamp
            context["scheduled_start_time"] = None
            context["scheduled_end_time"] = None
            context["status"] = working_status.WorkingStatus.C_KINMU
        elif is_over_half_working_hours(stamp, employee, (scheduled_start_time, scheduled_end_time)):
            # 出社打刻が勤務時間の半分以上なら、出勤打刻がないものとして扱う
            context["clock_in"] = None
            context["clock_out"] = stamp
            context["scheduled_start_time"] = scheduled_start_time
            context["scheduled_end_time"] = scheduled_end_time
            context["status"] = working_status.WorkingStatus.C_KINMU
        else:
            # 出社打刻が勤務時間の半分以下なら、退勤打刻がないものとして扱う
            context["clock_in"] = stamp
            context["clock_out"] = None
            context["scheduled_start_time"] = scheduled_start_time
            context["scheduled_end_time"] = scheduled_end_time
            context["status"] = working_status.WorkingStatus.C_KINMU
    elif len(stamps) >= 2:
        # 打刻が2件以上あるので、最初と最後を出社・退社として登録する
        first_stamp = stamps[0]
        last_stamp = stamps[-1]
        if core.is_holiday(date):
            context["clock_in"] = first_stamp
            context["clock_out"] = last_stamp
            context["scheduled_start_time"] = None
            context["scheduled_end_time"] = None
            context["status"] = working_status.WorkingStatus.C_KINMU
        else:
            context["clock_in"] = first_stamp
            context["clock_out"] = last_stamp
            context["scheduled_start_time"] = scheduled_start_time
            context["scheduled_end_time"] = scheduled_end_time
            context["status"] = working_status.WorkingStatus.C_KINMU

    models.EmployeeDailyRecord(
        employee=context["employee"],
        date=context["date"],
        clock_in=context["clock_in"],
        clock_out=context["clock_out"],
        scheduled_start_time = context["scheduled_start_time"],
        scheduled_end_time = context["scheduled_end_time"],
        status=context["status"],
    ).save()

def generate_attendance_record(record: models.EmployeeDailyRecord):
    """DailyAttendanceRecordを生成する"""
    attendance = models.DailyAttendanceRecord(time_record=record)
        
    # 所定の始業、終業、勤務時間を取得する
    begin_work = record.clock_in
    end_work = record.clock_out
    
    # 調整された出勤時間、退勤時間
    (begin_work, end_work) = core.adjust_working_hours(record)

    # 予定勤務時間
    assumed_working_time = core.calc_assumed_working_time(record, begin_work, end_work)

    # 実労働時間(休息分は差し引かれてる)
    actual_working_time = core.calc_actual_working_time(record, begin_work, end_work, const.Const.TD_ZERO)

    attendance.actual_working_time = actual_working_time
    attendance.late_time = core.calc_tardiness(record, begin_work)
    attendance.early_leave = core.calc_leave_early(record, end_work)
    attendance.over_time = core.calc_overtime(record, actual_working_time, assumed_working_time)
    if attendance.over_time is not None and attendance.over_time.total_seconds() > 0:
        attendance.over_8h = core.calc_over_8h(record, actual_working_time)
        attendance.night_work = core.calc_midnight_work(record)
    attendance.legal_holiday_work = core.calc_legal_holiday(record, actual_working_time)
    attendance.holiday_work = core.calc_holiday(record, actual_working_time)
    attendance.status = record.status
    attendance.save()
