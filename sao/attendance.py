import logging
import datetime

from sao.const import Const
from sao.working_status import WorkingStatus
from sao.models import DailyAttendanceRecord, Employee
from sao.period import Period

logger = logging.getLogger("sao")


class Attendance:
    """勤怠データを保持するクラス"""

    def __init__(
        self,
        date: datetime.date,
        employee: Employee,
        record: DailyAttendanceRecord | None = None,
    ):
        if isinstance(date, datetime.datetime):
            raise TypeError("date must be datetime.date")
        self.date = date  # 日付
        self.employee = employee  # 従業員
        self.daily_attendance_record = record if record else None  # 元データ
        self.clock_in = record.clock_in if record else None  # 打刻時間
        self.clock_out = record.clock_out if record else None  # 打刻時間
        self.raw_clock_in = (
            record.time_record.clock_in if record and record.time_record else None
        )  # 元打刻時間
        self.raw_clock_out = (
            record.time_record.clock_out if record and record.time_record else None
        )  # 元打刻時間
        self.working_hours_start = (
            record.working_hours_start if record else None
        )  # 勤務時間開始
        self.working_hours_end = (
            record.working_hours_end if record else None
        )  # 勤務時間終了
        self.actual_work = record.actual_work if record else Const.TD_ZERO  # 実労働時間
        self.late = record.late if record else Const.TD_ZERO  # 遅刻
        self.early_leave = record.early_leave if record else Const.TD_ZERO  # 早退
        self.stepping_out = record.stepping_out if record else Const.TD_ZERO  # 外出
        self.over = record.over if record else Const.TD_ZERO  # 時間外
        self.total_overtime = Const.TD_ZERO
        self.over_8h = (
            record.over_8h if record else Const.TD_ZERO
        )  # 割増=8時間を超えた分
        self.night = record.night if record else Const.TD_ZERO  # 深夜=10時以降
        self.legal_holiday = (
            record.legal_holiday if record else Const.TD_ZERO
        )  # 法定休日
        self.holiday = record.holiday if record else Const.TD_ZERO  # 法定外休日
        self.status = record.status if record else WorkingStatus.C_NONE
        self.overtime_permitted = (
            record.overtime_permitted if record else False
        )  # 残業許可

        # 以下、DailyAttendanceRecordにはない
        self.total_overtime = Const.TD_ZERO
        self.remark = ""  # 届け
        self.flag = ""
        self.is_absent = False
        self.warnings = {}

    def get_stamp(self) -> Period:
        return Period(self.clock_in, self.clock_out)

    def is_valid(self):
        if self.date is None:
            return False
        if self.status is WorkingStatus.C_NONE:
            return False
        return True

    def __str__(self):
        s = str(self.clock_in) + " "
        s += str(self.clock_out) + " "
        s += str(self.actual_work) + " "
        s += str(self.late) + " "
        return s
