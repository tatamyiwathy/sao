class NoAssignedWorkingHourError(Exception):
    """従業員に所定の勤務時間が設定されていない場合の例外"""

    def __init__(self, arg=""):
        self.arg = arg

    def __str__(self):
        return self.arg


class AnomalyTimeRecordError(Exception):
    """不正な打刻データがある場合の例外"""

    def __init__(self, arg=""):
        self.arg = arg

    def __str__(self):
        return self.arg
