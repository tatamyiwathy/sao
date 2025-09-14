import datetime
from django.db import models
from sao.models import Employee, EmployeeDailyRecord
from sao.working_status import WorkingStatus


class DailyAttendanceRecord(models.Model):
    """日次勤怠集計"""

    create_at = models.DateTimeField(default=datetime.datetime.now)
    update_at = models.DateTimeField(auto_now=True)

    time_record = models.OneToOneField(
        EmployeeDailyRecord, on_delete=models.PROTECT, related_name="time_record"
    )
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="employee",
    )
    # 対象日
    date = models.DateField(null=True, blank=True)
    # 調整後の時間
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    # 所定勤務時間
    working_hours_start = models.DateTimeField(null=True, blank=True)
    working_hours_end = models.DateTimeField(null=True, blank=True)
    # 実労働時間
    actual_work = models.DurationField(default=datetime.timedelta(0))
    # 遅刻
    late = models.DurationField(default=datetime.timedelta(0))
    # 早退
    early_leave = models.DurationField(default=datetime.timedelta(0))
    # 外出
    stepping_out = models.DurationField(default=datetime.timedelta(0))
    # 時間外労働
    over = models.DurationField(default=datetime.timedelta(0))
    # 割増=8時間を超えた分
    over_8h = models.DurationField(default=datetime.timedelta(0))
    # 深夜=22時以降
    night = models.DurationField(default=datetime.timedelta(0))
    # 法定休日
    legal_holiday = models.DurationField(default=datetime.timedelta(0))
    # 法定外休日
    holiday = models.DurationField(default=datetime.timedelta(0))
    # 届け
    remark = models.CharField(max_length=128, null=True, blank=True)
    # 勤務状況
    status = models.IntegerField(
        default=WorkingStatus.C_NONE, choices=WorkingStatus.choices
    )

    def __str__(self):
        if self.time_record is None:
            return "No TimeRecord"
        if self.time_record.employee is None:
            return "No Employee"
        return "%s %s" % (self.time_record.employee, self.time_record.date)

    def get_over(self) -> datetime.timedelta:
        return self.over
