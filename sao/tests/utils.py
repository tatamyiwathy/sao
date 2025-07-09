import sao.models as models
import sao.calendar as calendar
import datetime

from sao.working_status import WorkingStatus


def create_working_hours():
    """勤務時間種別テーブル作成"""

    models.WorkingHour(
        begin_time=datetime.time(10, 0, 0),
        end_time=datetime.time(19, 0, 0),
        category="A",
    ).save()

    models.WorkingHour(
        begin_time=datetime.time(9, 30, 0),
        end_time=datetime.time(17, 30, 0),
        category="E",
    ).save()

    models.WorkingHour(
        begin_time=datetime.time(10, 30, 0),
        end_time=datetime.time(19, 30, 0),
        category="H",
    ).save()


def set_office_hours_to_employee(
    employee: models.Employee,
    date_from: datetime.date,
    working_hours: models.WorkingHour,
) -> models.AppliedOfficeHours:
    """
    スタッフに勤務時間を設定する

    WorkingHoursから設定したい時間帯を選択して
    有効になる日付を指定して設定する

    """
    t = models.AppliedOfficeHours(
        employee=employee, date=date_from, working_hours=working_hours
    )
    t.save()
    return t


def create_timerecord(**kwargs) -> models.TimeRecord:
    """タイムレコード作成
    stamp: [出勤打刻, 退社打刻]
    status: WorkingStatus
    date: 打刻日時
    adjusted_clock_in: datetime.time
    adjusted_clock_out: datetime.time
    employee: models.Employee

    """

    clock_in = None
    clock_out = None
    status = WorkingStatus.C_NONE
    adjusted_clockin = None
    adjusted_clockout = None

    if kwargs["stamp"][0] is not None:
        clock_in = datetime.datetime.combine(kwargs["date"], kwargs["stamp"][0])

    if kwargs["stamp"][1] is not None:
        clock_out = datetime.datetime.combine(kwargs["date"], kwargs["stamp"][1])

    if None not in [clock_in, clock_out]:
        # 退社打刻がAM0:00-4:59の時は日付を次の日にする
        if clock_in > clock_out:
            if clock_out.time() < datetime.time(hour=5):
                clock_out += datetime.timedelta(days=1)
            else:
                raise ValueError("fromTime > toTime")

    if "status" in kwargs:
        status = kwargs["status"]
    else:
        if calendar.is_holiday(kwargs["date"]):
            if None not in [clock_in, clock_out]:
                if calendar.is_legal_holiday(kwargs["date"]):
                    # 日曜出勤
                    status = WorkingStatus.C_HOUTEI_KYUJITU
                else:
                    # 土曜・祝日出勤
                    status = WorkingStatus.C_HOUTEIGAI_KYUJITU
            else:
                status = WorkingStatus.C_KYUJITU
        else:
            if [clock_in, clock_out] == [None, None]:
                # 平日で記録なし
                status = WorkingStatus.C_KEKKIN
            else:
                status = WorkingStatus.C_KINMU

    if "adjusted_clock_in" in kwargs.keys() and kwargs["adjusted_clock_in"] is not None:
        adjusted_clockin = datetime.datetime.combine(
            kwargs["date"], kwargs["adjusted_clock_in"]
        )
    if (
        "adjusted_clock_out" in kwargs.keys()
        and kwargs["adjusted_clock_out"] is not None
    ):
        adjusted_clockout = datetime.datetime.combine(
            kwargs["date"], kwargs["adjusted_clock_out"]
        )

    if None not in [adjusted_clockin, adjusted_clockout]:
        if adjusted_clockin > adjusted_clockout:
            raise ValueError("clockin > clockout")

    accepted_overtime = True if adjusted_clockin and adjusted_clockout else False

    timerecord = models.TimeRecord(
        date=kwargs["date"],
        employee=kwargs["employee"],
        clock_in=clock_in,
        clock_out=clock_out,
        status=status,
        is_overtime_work_permitted=accepted_overtime,
    )
    timerecord.save()
    return timerecord


def create_time_stamp_data(employee: models.Employee):
    """テスト用のタイムシートデータを生成する"""
    TEST_STAMP = [
        ("2021/8/1", None, None),
        ("2021/8/2", "13:00:00", "19:00:00"),  # 遅刻 6h勤務
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
        create_timerecord(
            employee=employee,
            date=date,
            stamp=[clock_in, clock_out],
        )


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
