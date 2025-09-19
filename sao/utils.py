import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from sao import core
from sao.attendance import Attendance
from sao.period import Period
from sao.calendar import is_legal_holiday, is_holiday
from sao.const import Const
from sao.models import (
    DailyAttendanceRecord,
    Employee,
    WebTimeStamp,
    WorkingHour,
    EmployeeHour,
    SteppingOut,
)


def make_web_stamp_string(employee: Employee, date: datetime.date) -> tuple[str, str]:
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
    stamps = WebTimeStamp.objects.filter(
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
    if type == Employee.TYPE_PERMANENT_STAFF:
        name = "正社員"
    elif type == Employee.TYPE_TEMPORARY_STAFF:
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
    if type == Employee.DEPT_GENERAL:
        name = "一般"
    elif type == Employee.DEPT_DEVELOPMENT:
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


def create_employee(**kwargs) -> Employee:
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
    employee = Employee(
        employee_no=kwargs["employee_no"],
        name=kwargs["name"],
        join_date=join_date,
        leave_date=leave_date,
        payed_holiday=payed_holiday,
        employee_type=kwargs["employee_type"],
        department=kwargs["department"],
        user=kwargs["user"],
    )
    employee.save()
    return employee


def get_employee_status_display(employee: Employee, date: datetime.date) -> str:
    """雇用者のステータスを文字列にする

    :param employee: 雇用者
    :param date: 判定日
    :return: ステータスの文字列"""
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


def is_missed_stamp(
    clock_in: datetime.datetime | None, clock_out: datetime.datetime | None
) -> bool:
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


def is_empty_stamp(
    clock_in: datetime.datetime | None, clock_out: datetime.datetime | None
) -> bool:
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


def tally_attendances(attendances: list[Attendance]) -> dict:
    """
    勤務評価結果の集計をする

    :param attendances: 勤怠記録のリスト
    :return: 集計結果の辞書
    """

    attendance_tallied = {
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
            attendance_tallied["work"] += attn.actual_work
            attendance_tallied["late"] += attn.late
            attendance_tallied["before"] += attn.early_leave
            attendance_tallied["steppingout"] += attn.stepping_out
            attendance_tallied["out_of_time"] += attn.over
            attendance_tallied["over_8h"] += attn.over_8h
            attendance_tallied["night"] += attn.night
            attendance_tallied["legal_holiday"] += attn.legal_holiday
            attendance_tallied["holiday"] += attn.holiday

            if not is_legal_holiday(attn.date):
                attendance_tallied["accumulated_overtime"] += attn.over
    return attendance_tallied


def setup_sample_data() -> None:
    """サンプルデータを生成する"""

    sample_stamp = [
        # (日)
        ("2021/8/1", None, None),
        ("2021/8/2", "13:00:00", "19:00:00"),  # （月）遅刻 6h勤務
        ("2021/8/3", "9:40:00", "20:00:00"),  # 1hour overtime work
        ("2021/8/4", "9:35:00", "19:47:00"),
        ("2021/8/5", "9:38:00", "20:32:00"),
        ("2021/8/6", "9:46:00", "20:13:00"),
        ("2021/8/7", None, None),
        # (日)
        ("2021/8/8", None, None),
        ("2021/8/9", None, None),  # 祝日
        ("2021/8/10", "9:46:00", "20:41:00"),
        ("2021/8/11", "9:50:00", "21:31:00"),
        ("2021/8/12", None, None),
        ("2021/8/13", None, None),
        ("2021/8/14", None, None),
        # (日)
        ("2021/8/15", None, None),
        ("2021/8/16", None, None),
        ("2021/8/17", None, None),
        ("2021/8/18", "9:47:00", "19:27:00"),
        ("2021/8/19", "9:56:00", "19:45:00"),
        ("2021/8/20", "9:53:00", "19:27:00"),
        (
            "2021/8/21",
            "9:32:00",
            "12:45:00",
        ),  # 法定外休出　修正
        # (日)
        ("2021/8/22", None, None),
        ("2021/8/23", None, None),  # 欠勤
        ("2021/8/24", "9:55:00", "18:36:00"),  # 早退
        ("2021/8/25", "9:50:00", "19:28:00"),
        ("2021/8/26", "9:56:00", "19:54:00"),
        ("2021/8/27", "9:55:00", "19:53:00"),
        ("2021/8/28", None, None),
        # (日)
        ("2021/8/29", None, None),
        ("2021/8/30", "9:55:00", "19:37:00"),
        ("2021/8/31", "9:51:00", "22:51:00"),  # over 10:00pm
    ]

    from django.contrib.auth import get_user_model

    User = get_user_model()
    if User.objects.filter(username="foobar").exists():
        return

    user = create_user("foobar", "山田", "太郎", "foobar", "foobartaro@example.com")
    user.permission.enable_stamp_on_web = True  # type: ignore
    user.save()

    employee = create_employee(
        employee_no=1,
        name="山田 太郎",
        employee_type=Employee.TYPE_PERMANENT_STAFF,
        department=Employee.DEPT_GENERAL,
        user=user,
        join_date=datetime.date(2021, 1, 1),
        payed_holiday=10.0,
    )

    core.assign_fixed_overtime_pay(employee, Const.FIXED_OVERTIME_HOURS_20)
    if not core.has_assigned_fixed_overtime_pay(employee):
        raise ValueError("Failed to assign fixed overtime pay")

    working_hours = WorkingHour(
        begin_time=datetime.time(10, 0, 0),
        end_time=datetime.time(19, 0, 0),
        category="総務",
    )
    working_hours.save()

    EmployeeHour.objects.create(
        employee=employee, date=datetime.date(2021, 1, 1), working_hours=working_hours
    )

    for stamp in sample_stamp:
        date = datetime.datetime.strptime(stamp[0], "%Y/%m/%d").date()
        clock_in = (
            datetime.datetime.strptime(stamp[1], "%H:%M:%S").time()
            if stamp[1]
            else None
        )
        clock_out = (
            datetime.datetime.strptime(stamp[2], "%H:%M:%S").time()
            if stamp[2]
            else None
        )
        if clock_in:
            clock_in = datetime.datetime.combine(date, clock_in)
        if clock_out:
            clock_out = datetime.datetime.combine(date, clock_out)

        record = core.generate_daily_record([clock_in, clock_out], employee, date)
        if record:
            attendance = core.generate_attendance_record(record)
            attendance = core.initiate_daily_attendance_record(attendance)
            attendance = core.update_attendance_record(attendance)


import random


class AnomalyType:
    NORMAL = 1
    LATE = 2
    EARLY_LEAVE = 3
    MISSED_CLOCK_IN = 4
    MISSED_CLOCK_OUT = 5
    HOLIDAY_WORK = 6
    LEGAL_HOLIDAY_WORK = 7


def get_anomaly_stamp_type() -> int:
    """異常打刻の種類をランダムに返す"""
    r = random.randint(1, 30)
    # 1 late
    # 2 early leave
    # 3 missed clock in
    # 4 missed clock out
    return r


def generate_sample_data(employee: Employee, year: int, month: int) -> None:
    """指定した年月のサンプルデータを生成する"""

    def make_late_stamp(d):
        r = random.randint(1, 60 * 3)
        clock_in = datetime.datetime.combine(
            d, datetime.time(10, 0)
        ) + datetime.timedelta(minutes=r)
        r = random.randint(0, 3600)
        clock_out = datetime.datetime.combine(
            d, datetime.time(19, 0)
        ) + datetime.timedelta(seconds=r)
        return clock_in, clock_out

    def make_early_leave_stamp(d):
        r = random.randint(0, 3600)
        clock_in = datetime.datetime.combine(
            d, datetime.time(10, 0)
        ) + datetime.timedelta(seconds=r)
        r = random.randint(60, 60 * 3)
        clock_out = datetime.datetime.combine(
            d, datetime.time(19, 0)
        ) - datetime.timedelta(minutes=r)
        return clock_in, clock_out

    def make_missed_clock_in_stamp(d):
        clock_in = None
        r = random.randint(0, 3600)
        clock_out = datetime.datetime.combine(
            d, datetime.time(19, 0)
        ) + datetime.timedelta(seconds=r)
        return clock_in, clock_out

    def make_missed_clock_out_stamp(d):
        r = random.randint(0, 3600)
        clock_in = datetime.datetime.combine(
            d, datetime.time(10, 0)
        ) + datetime.timedelta(seconds=r)
        clock_out = None
        return clock_in, clock_out

    def make_normal_stamp(d):
        r = random.randint(-300, 300)
        clock_in = datetime.datetime.combine(
            d, datetime.time(9, 50)
        ) + datetime.timedelta(seconds=r)
        r = random.randint(0, 3600)
        clock_out = datetime.datetime.combine(
            d, datetime.time(19, 0)
        ) + datetime.timedelta(seconds=r)
        return clock_in, clock_out

    STAMP_GENERATORS = {
        1: make_late_stamp,
        2: make_early_leave_stamp,
        3: make_missed_clock_in_stamp,
        4: make_missed_clock_out_stamp,
    }

    from django.contrib.auth import get_user_model

    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month + 1, 1)

    period = Period(
        datetime.datetime.combine(start_date, datetime.time.min),
        datetime.datetime.combine(end_date, datetime.time.min),
    )

    for d in period.range():
        if d >= datetime.datetime.now() - datetime.timedelta(days=1):
            break

        if is_holiday(d.date()):
            if random.randint(1, 10) != 1:
                # 休日は打刻しない
                continue
            clock_in = datetime.datetime.combine(d, datetime.time(11, 30))
            clock_out = datetime.datetime.combine(d, datetime.time(17, 15))
        else:
            anomaly_type = get_anomaly_stamp_type()
            stamp_func = STAMP_GENERATORS.get(anomaly_type, make_normal_stamp)
            clock_in, clock_out = stamp_func(d.date())

        record = core.generate_daily_record([clock_in, clock_out], employee, d.date())
        if record:
            attendance = core.generate_attendance_record(record)
            attendance = core.initiate_daily_attendance_record(attendance)
            attendance = core.update_attendance_record(attendance)


def get_stepout_record(
    employee: Employee, clock_in: datetime.datetime, clock_out: datetime.datetime
):
    day_start = (
        clock_in
        if clock_in
        else datetime.datetime.combine(record.date, datetime.time(hour=5))
    )
    day_end = (
        clock_out
        if clock_out
        else datetime.datetime.combine(record.date, datetime.time(hour=5))
        + datetime.timedelta(days=1)
    )
    return SteppingOut.objects.filter(
        employee=employee, out_time__gte=day_start, return_time__lt=day_end
    )
