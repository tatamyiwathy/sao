import logging
import datetime
from .calendar import is_legal_holiday
from .const import Const
from .utils import is_missed_stamp
from .working_status import WorkingStatus
from .models import EmployeeDailyRecord
from .core import (
    adjust_working_hours,
    calc_assumed_working_time,
    tally_steppingout,
    calc_actual_working_time,
    calc_tardiness,
    calc_leave_early,
    calc_overtime,
    calc_over_8h,
    calc_midnight_work,
    calc_legal_holiday,
    calc_holiday
)

logger = logging.getLogger("sao")

class Attendance:
    """勤怠データを保持するクラス"""

    def __init__(self, record=None):
        self.date = None
        self.clock_in = None  # 実打刻時間
        self.clock_out = None
        self.actual_work = Const.TD_ZERO  # 実労働時間
        self.late = Const.TD_ZERO  # 遅刻
        self.early_leave = Const.TD_ZERO  # 早退
        self.stepping_out = Const.TD_ZERO  # 外出
        self.over = Const.TD_ZERO  # 時間外
        self.over_8h = Const.TD_ZERO  # 割増=8時間を超えた分
        self.night = Const.TD_ZERO  # 深夜=10時以降
        self.legal_holiday = Const.TD_ZERO  # 法定休日
        self.holiday = Const.TD_ZERO  # 法定外休日
        self.remark = ""  # 届け
        self.status = WorkingStatus.C_NONE
        self.flag = ""
        self.is_absent = False
        self.warnings = {}




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

    def is_missing_stamp(self):
        if self.status is not WorkingStatus.C_KINMU:
            return False
        return is_missed_stamp(self.clock_in, self.clock_out)

def tally_monthly_attendance(month: int, records: list[EmployeeDailyRecord]) -> list[Attendance]:
    """TimeRecordからAttendanceを作成する
    month: 対象月
    records: TimeRecordのリスト

    employeeの所定労働時間が設定されていない場合はNoSpecifiedWorkingHoursErrorが発生する
    """
    result_record = []

    summed_out_of_time = datetime.timedelta()
    for r in records:
        if r.date.month != month:
            # 対象月の記録ではないので何もしない
            continue
        # 所定労働時間を取得
        attendance = generate_attendance(r)
        summed_out_of_time += attendance.out_of_time
        attendance.summed_out_of_time = summed_out_of_time
        result_record.append(attendance)
    return result_record


def sumup_attendances(attendances: list[Attendance]) -> dict:
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
        if attn.work:
            summed_up["work"] += attn.work
            summed_up["late"] += attn.late
            summed_up["before"] += attn.before
            summed_up["steppingout"] += attn.steppingout
            summed_up["out_of_time"] += attn.out_of_time
            summed_up["over_8h"] += attn.over_8h
            summed_up["night"] += attn.night
            summed_up["legal_holiday"] += attn.legal_holiday
            summed_up["holiday"] += attn.holiday

            if not is_legal_holiday(attn.date):
                summed_up["accumulated_overtime"] += attn.out_of_time
    return summed_up


