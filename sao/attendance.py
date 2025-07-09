from .const import Const
from .utils import is_missed_stamp
from .working_status import WorkingStatus


class Attendance:
    """勤怠データを保持するクラス"""

    def __init__(self):
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
