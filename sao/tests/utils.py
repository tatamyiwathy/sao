import datetime

from sao.models import Employee, WorkingHour, EmployeeHour,EmployeeDailyRecord, DailyAttendanceRecord
from sao.calendar import is_holiday,is_legal_holiday
from sao.core import generate_attendance_record, get_day_switch_time
from sao.period import Period
from sao.working_status import WorkingStatus, get_working_status
from sao.attendance import Attendance


def create_working_hours():
    """勤務時間種別テーブル作成"""

    WorkingHour(
        begin_time=datetime.time(10, 0, 0),
        end_time=datetime.time(19, 0, 0),
        category="A",
    ).save()

    WorkingHour(
        begin_time=datetime.time(9, 30, 0),
        end_time=datetime.time(17, 30, 0),
        category="E",
    ).save()

    WorkingHour(
        begin_time=datetime.time(10, 30, 0),
        end_time=datetime.time(19, 30, 0),
        category="H",
    ).save()


def set_office_hours_to_employee(
    employee: Employee,
    date_from: datetime.date,
    working_hours: WorkingHour,
) -> EmployeeHour:
    """
    スタッフに勤務時間を設定する

    WorkingHoursから設定したい時間帯を選択して
    有効になる日付を指定して設定する

    """
    t = EmployeeHour(
        employee=employee, date=date_from, working_hours=working_hours
    )
    t.save()
    return t


def create_timerecord(**kwargs) -> EmployeeDailyRecord:
    """タイムレコード作成
    stamp: datetime [出勤打刻, 退社打刻]
    working_hours: datetime [開始、終了]
    status: WorkingStatus
    date: 打刻日時
    employee: Employee

    """

    clock_in = kwargs["stamp"][0] if "stamp" in kwargs else None
    clock_out = kwargs["stamp"][1] if "stamp" in kwargs else None
    working_hours_start = kwargs["working_hours"][0] if "working_hours" in kwargs else None
    working_hours_end = kwargs["working_hours"][1] if "working_hours" in kwargs else None
    status = kwargs["status"] if "status" in kwargs else None

    timerecord = EmployeeDailyRecord(
        date=kwargs["date"],
        employee=kwargs["employee"],
        clock_in=clock_in,
        clock_out=clock_out,
        working_hours_start=working_hours_start,
        working_hours_end=working_hours_end,
        status=status,

    )
    timerecord.save()
    return timerecord

def create_attendance_record(time_record: EmployeeDailyRecord) -> DailyAttendanceRecord:
    if time_record is None:
        raise ValueError("time_record is None")
    attn = generate_attendance_record(time_record)
    return attn

def create_time_stamp_data(employee: Employee):
    """テスト用のタイムシートデータを生成する"""
    TEST_STAMP = [
        ("2021/8/1", None, None),
        ("2021/8/2", "13:00:00", "19:00:00"),  # （月）遅刻 6h勤務
        ("2021/8/3", "9:40:00", "20:00:00"),  # 1hour overtime work
        ("2021/8/4", "9:35:00", "19:47:00"),
        ("2021/8/5", "9:38:00", "20:32:00"),
        ("2021/8/6", "9:46:00", "20:13:00"),
        ("2021/8/7", None, None),
        ("2021/8/8", None, None),
        ("2021/8/9", None, None),  # 祝日
        ("2021/8/10", "9:46:00", "20:41:00"),
        ("2021/8/11", "9:50:00", "21:31:00"),
        ("2021/8/12", None, None),
        ("2021/8/13", None, None),
        ("2021/8/14", None, None),
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
        ("2021/8/22", None, None),  # (日)
        ("2021/8/23", None, None),  # 欠勤
        ("2021/8/24", "9:55:00", "18:36:00"),  # 早退
        ("2021/8/25", "9:50:00", "19:28:00"),
        ("2021/8/26", "9:56:00", "19:54:00"),
        ("2021/8/27", "9:55:00", "19:53:00"),
        ("2021/8/28", None, None),
        ("2021/8/29", None, None),
        ("2021/8/30", "9:55:00", "19:37:00"),
        ("2021/8/31", "9:51:00", "22:51:00"),  # over 10:00pm
    ]

    for stamp in TEST_STAMP:
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
        working_hours_start = datetime.datetime.combine(date, datetime.time(10, 0, 0))
        working_hours_end = datetime.datetime.combine(date, datetime.time(19, 0, 0))

        record = create_timerecord(
                employee=employee,
                date=date,
                stamp=[clock_in, clock_out],
                working_hours=[working_hours_start, working_hours_end])
        
        attendance = create_attendance_record(record)


def to_timedelta(time: datetime.datetime) -> datetime.timedelta:
    return datetime.timedelta(hours=time.hour, minutes=time.minute, seconds=time.second)


ACTUAL_WORKING_TIME_SAMPLE = [
    (
        "2021/8/1",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/2",
        to_timedelta(datetime.datetime.strptime("06:00", "%H:%M")),
    ),
    (
        "2021/8/3",
        to_timedelta(datetime.datetime.strptime("09:00", "%H:%M")),
    ),
    (
        "2021/8/4",
        to_timedelta(datetime.datetime.strptime("08:47", "%H:%M")),
    ),
    (
        "2021/8/5",
        to_timedelta(datetime.datetime.strptime("09:32", "%H:%M")),
    ),
    (
        "2021/8/6",
        to_timedelta(datetime.datetime.strptime("09:13", "%H:%M")),
    ),
    (
        "2021/8/7",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/8",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/9",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/10",
        to_timedelta(datetime.datetime.strptime("09:41", "%H:%M")),
    ),
    (
        "2021/8/11",
        to_timedelta(datetime.datetime.strptime("10:31", "%H:%M")),
    ),
    (
        "2021/8/12",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/13",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/14",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/15",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/16",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/17",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/18",
        to_timedelta(datetime.datetime.strptime("08:27", "%H:%M")),
    ),
    (
        "2021/8/19",
        to_timedelta(datetime.datetime.strptime("08:45", "%H:%M")),
    ),
    (
        "2021/8/20",
        to_timedelta(datetime.datetime.strptime("08:27", "%H:%M")),
    ),
    (
        "2021/8/21",
        to_timedelta(datetime.datetime.strptime("03:13", "%H:%M")),
    ),
    (
        "2021/8/22",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/23",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/24",
        to_timedelta(datetime.datetime.strptime("07:36", "%H:%M")),
    ),
    (
        "2021/8/25",
        to_timedelta(datetime.datetime.strptime("08:28", "%H:%M")),
    ),
    (
        "2021/8/26",
        to_timedelta(datetime.datetime.strptime("08:54", "%H:%M")),
    ),
    (
        "2021/8/27",
        to_timedelta(datetime.datetime.strptime("08:53", "%H:%M")),
    ),
    (
        "2021/8/28",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/29",
        to_timedelta(datetime.datetime.strptime("00:00", "%H:%M")),
    ),
    (
        "2021/8/30",
        to_timedelta(datetime.datetime.strptime("08:37", "%H:%M")),
    ),
    (
        "2021/8/31",
        to_timedelta(datetime.datetime.strptime("11:51", "%H:%M")),
    ),
]

TOTAL_ACTUAL_WORKING_TIME = sum(
    [x[1] for x in ACTUAL_WORKING_TIME_SAMPLE], datetime.timedelta(seconds=0)
)


