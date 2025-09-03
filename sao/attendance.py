import logging
import datetime
from .calendar import is_legal_holiday
from .const import Const
from .utils import is_missed_stamp
from .working_status import WorkingStatus
from .models import EmployeeDailyRecord
from .core import (
    adjust_working_hours,
    get_assumed_working_time,
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
        self.adjusted_from = None  # 調整後の時間
        self.adjusted_to = None  #
        self.work = Const.TD_ZERO  # 実労働時間
        self.late = Const.TD_ZERO  # 遅刻
        self.before = Const.TD_ZERO  # 早退
        self.steppingout = Const.TD_ZERO  # 外出
        self.out_of_time = Const.TD_ZERO  # 時間外
        self.summed_out_of_time = Const.TD_ZERO  # 積算時間外
        self.over_8h = Const.TD_ZERO  # 割増=8時間を超えた分
        self.night = Const.TD_ZERO  # 深夜=10時以降
        self.legal_holiday = Const.TD_ZERO  # 法定休日
        self.holiday = Const.TD_ZERO  # 法定外休日
        self.accumulated_overtime = 0
        self.accepted_overtime = 0  # 残業届け済み
        self.remark = ""  # 届け
        self.eval_code = WorkingStatus.C_NONE
        self.record_id = 0
        self.flag = ""
        self.is_absent = False
        self.warnings = {}



        # 所定の始業、終業、勤務時間を取得する
        (begin_work, end_work) = adjust_working_hours(record)
        working_time = get_assumed_working_time(record, begin_work, end_work)

        # 外出時間
        steppingout = tally_steppingout(record)

        # 実労働時間(休息分は差し引かれてる)
        actual_work = calc_actual_working_time(record, begin_work, end_work, steppingout)

        self.date = record.date
        self.remark = record.remark
        self.eval_code = record.status
        self.work = actual_work
        self.late = calc_tardiness(record, begin_work)
        self.before = calc_leave_early(record, end_work)
        self.steppingout = steppingout
        self.out_of_time = calc_overtime(record, actual_work, working_time)
        if self.out_of_time.total_seconds() > 0:
            self.over_8h = calc_over_8h(record, actual_work)
            self.night = calc_midnight_work(record)
        self.legal_holiday = calc_legal_holiday(record, actual_work)
        self.holiday = calc_holiday(record, actual_work)
        self.date = record.date
        self.clock_in = record.get_clock_in().time() if record.get_clock_in() else None
        self.clock_out = record.get_clock_out().time() if record.get_clock_out() else None
        self.record_id = record.id

        self.is_absent = False
        if self.eval_code in [
            WorkingStatus.C_KEKKIN,
            WorkingStatus.C_YUUKYUU,
            WorkingStatus.C_DAIKYUU,
            WorkingStatus.C_TOKUBETUKYUU,
        ]:
            self.is_absent = True
        self.accepted_overtime = record.is_overtime_work_permitted




    def is_valid(self):
        if self.date is None:
            return False
        if self.eval_code is WorkingStatus.C_NONE:
            return False
        return True

    def __str__(self):
        s = str(self.clock_in) + " "
        s += str(self.clock_out) + " "
        s += str(self.work) + " "
        s += str(self.late) + " "
        return s

    def is_missing_stamp(self):
        if self.eval_code is not WorkingStatus.C_KINMU:
            return False
        return is_missed_stamp(self.clock_in, self.clock_out)

def generate_attendance(record: EmployeeDailyRecord) -> Attendance:
    if not record.is_valid_status():
        logger.warning("勤怠記録(%s)とeval_code(%s)が不一致" % (record, record.status))
    return Attendance(record)


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


