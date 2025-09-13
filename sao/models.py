import datetime
from typing import Any
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from sao.calendar import is_holiday
from sao.working_status import WorkingStatus
from sao.period import Period


class Employee(models.Model):
    """社員クラス"""

    TYPE_PERMANENT_STAFF = 0
    TYPE_TEMPORARY_STAFF = 1
    TYPE_OUTSOURCING_STAFF = 2

    STAFF_TYPE_CHOICES = [
        (TYPE_PERMANENT_STAFF, "正社員"),
        (TYPE_TEMPORARY_STAFF, "派遣社員"),
        (TYPE_OUTSOURCING_STAFF, "業務委託"),
    ]

    DEPT_GENERAL = 0
    DEPT_DEVELOPMENT = 1

    DEPARTMENT_CHOICES = [
        (DEPT_GENERAL, "一般"),
        (DEPT_DEVELOPMENT, "開発"),
    ]

    # 社員番号
    employee_no = models.IntegerField(unique=True)
    # 氏名
    name = models.CharField(max_length=20)
    # 有給残日
    payed_holiday = models.FloatField()
    # 入社日
    join_date = models.DateField()
    # 退社日
    leave_date = models.DateField()
    # ユーザーID
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee")
    # 雇用種別
    employee_type = models.IntegerField(default=0, choices=STAFF_TYPE_CHOICES)
    # 所属
    department = models.IntegerField(default=0, choices=DEPARTMENT_CHOICES)
    # 含み残業があるか
    # include_overtime_pay = models.BooleanField(default=True)

    def is_valid(self) -> bool:
        if self.employee_no is None:
            return False
        if self.name is None:
            return False
        if self.payed_holiday is None:
            return False
        if self.join_date is None:
            return False
        if self.leave_date is None:
            return False
        if self.user is None:
            return False
        if self.employee_type is None:
            return False
        if self.department is None:
            return False
        return True

    def __str__(self) -> str:
        return self.name

    # 管理職かどうか
    def is_manager(self) -> bool:
        try:
            manager = self.manager_set.get(manager=self)
        except ObjectDoesNotExist:
            manager = None
        return True if manager is not None else False

    def get_user_identify(self) -> str:
        return "%s(%d)" % (self.user, self.employee_no)


class Manager(models.Model):
    """マネージャ職"""

    manager = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.manager.name


class WorkingHour(models.Model):
    """勤務時間クラス"""

    category = models.CharField(r"区分", max_length=10, unique=True)
    begin_time = models.TimeField(r"出社時間")
    end_time = models.TimeField(r"退社時間")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return (
            self.category
            + ":"
            + str(self.begin_time)[:5]
            + "-"
            + str(self.end_time)[:5]
        )

    def is_valid(self):
        if not self.is_active:
            return False
        if self.begin_time is None:
            return False
        if self.end_time is None:
            return False
        return self.begin_time < self.end_time

    def get_paired_time(self, date: datetime.date) -> Period:
        """勤務時間の始業と終業をペアで取得する
        引数:
            date    対象の日付
        戻り値:
            Period    始業と終業のペア
        例外:
            ValueError  勤務時間が不正
        """
        if not self.is_valid():
            raise ValueError("Invalid working hour")
        start = datetime.datetime.combine(date, self.begin_time)
        end = datetime.datetime.combine(date, self.end_time)
        return Period(start=start, end=end)


class EmployeeDailyRecord(models.Model):
    """就業実績クラス"""

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    date = models.DateField()

    # 打刻した時間
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)

    # 所定の勤務時間
    working_hours_start = models.DateTimeField(null=True, blank=True)
    working_hours_end = models.DateTimeField(null=True, blank=True)

    # 勤務状況
    status = models.IntegerField(null=True, blank=True, choices=WorkingStatus.choices)

    # 届
    remark = models.CharField(max_length=128, null=True, blank=True)

    def is_valid(self) -> bool:
        """レコードが有効かどうか

        - employee, date, statusが設定されていること
        """
        if self.employee is None:
            return False
        if self.date is None:
            return False
        if self.status is None:
            return False
        # 打刻が無くても記録としては有効（休日とか病欠とかで打刻がないことがある）
        return True

    def __str__(self) -> str:
        return (
            self.employee.name
            + " "
            + str(self.date)
            + " "
            + str(self.clock_in)
            + " "
            + str(self.clock_out)
        )

    def get_clock_in(self) -> datetime.datetime | None:
        if self.clock_in is None:
            return None
        return self.clock_in.replace(second=0, microsecond=0)

    def get_clock_out(self) -> datetime.datetime | None:
        if self.clock_out is None:
            return None
        return self.clock_out.replace(second=0, microsecond=0)

    def get_clock_in_out(self) -> Period:
        """出退勤のペアを取得する"""
        return Period(start=self.get_clock_in(), end=self.get_clock_out())

    def get_scheduled_time(self) -> Period:
        """予定勤務時間のペアを取得する"""
        return Period(start=self.working_hours_start, end=self.working_hours_end)

    # 休日出勤か
    def is_holidaywork(self) -> bool:
        if self.status is WorkingStatus.C_NONE:
            return False
        if self.status not in WorkingStatus.HOLIDAY_WORK:
            return False
        return True

    def is_valid_status(self) -> bool:
        """statusを検査する
        ・打刻日が休日なのにstatusが休出でない
        ・打刻日が平日なのにstatusが休出
        ・打刻日が土曜なのにstatusが休出（法定）
        """
        d = datetime.date(self.date.year, self.date.month, self.date.day)
        if is_holiday(d):
            if self.status in [WorkingStatus.C_KINMU, WorkingStatus.C_KEKKIN]:
                # 休日なのに勤務したこになっている
                return False
            if d.weekday() == 5:  # 土曜日
                if self.status in [
                    WorkingStatus.C_HOUTEI_KYUJITU,
                    WorkingStatus.C_HOUTEI_KYUJITU_GOZENKYUU,
                    WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
                    WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_ARI,
                ]:
                    # 土曜なのに法定休日
                    return False
            elif d.weekday() == 6:  # 日曜日
                if self.status in [
                    WorkingStatus.C_HOUTEIGAI_KYUJITU,
                    WorkingStatus.C_HOUTEIGAI_KYUJITU_GOZENKYUU,
                    WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
                    WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
                ]:
                    # 日曜なのに法定外休日
                    return False
            elif self.status not in [
                WorkingStatus.C_KYUJITU,
                WorkingStatus.C_HOUTEI_KYUJITU,
                WorkingStatus.C_HOUTEI_KYUJITU_GOZENKYUU,
                WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
                WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_ARI,
                WorkingStatus.C_HOUTEIGAI_KYUJITU,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOZENKYUU,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
            ]:
                # 休日以外のコード
                return False
        else:
            if self.status in [
                WorkingStatus.C_KYUJITU,
                WorkingStatus.C_HOUTEI_KYUJITU,
                WorkingStatus.C_HOUTEI_KYUJITU_GOZENKYUU,
                WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
                WorkingStatus.C_HOUTEI_KYUJITU_GOGOKYU_ARI,
                WorkingStatus.C_HOUTEIGAI_KYUJITU,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOZENKYUU,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
                WorkingStatus.C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
            ]:
                # 平日なのに休日コード
                return False

        # ステータスは有効
        return True


class EmployeeHour(models.Model):
    """割り当てられた勤務時間"""

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    working_hours = models.ForeignKey("WorkingHour", on_delete=models.CASCADE)
    date = models.DateField()  # 適用日

    def __str__(self):
        return "%s %s %s" % (self.employee, self.date, self.working_hours)


class Notification(models.Model):
    """通知"""

    # 申請日
    filing_date = models.DateField("申請日")
    # 氏名
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    # 区分
    CATEGORY_CHOICES = (
        ("1", "残業"),
        ("2", "有給休暇"),
        ("3", "代休届"),
        ("4", "生理休暇"),
        ("5", "慶弔休暇"),
        ("6", "特別休暇"),
        ("7", "欠勤"),
        ("8", "遅刻"),
        ("9", "早退"),
        ("10", "私用外出"),
        ("11", "出張"),
        ("12", "休日出勤"),
    )
    category = models.IntegerField(choices=CATEGORY_CHOICES)

    # 期間    term
    begin_date = models.DateField("開始日時")
    begin_time = models.TimeField("開始時間")
    end_date = models.DateField("終了日時")
    end_time = models.TimeField("終了時間")

    # 事由    reason

    def __str__(self):
        return self.category


class Permission(models.Model):
    """権限"""

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # WEB打刻 - WEBでの打刻の許可
    enable_stamp_on_web = models.BooleanField(default=False)
    # ホームページの詳細表示 - 自分自身の詳細な勤怠記録の閲覧許可
    enable_view_detail = models.BooleanField(default=True)
    # 派遣社員マネージャ - 派遣スタッフの勤怠記録閲覧の許可
    enable_view_temporary_staff_record = models.BooleanField(default=False)
    # 一般社員マネージャ - 開発スタッフの「時間外」の閲覧の許可
    enable_view_dev_staff_record = models.BooleanField(default=False)
    # 業務委託マネージャー - 業務委託スタッフの勤怠記録閲覧の許可
    enable_view_outsource_staff_record = models.BooleanField(default=False)
    # 予定登録
    enable_regist_event = models.BooleanField(default=False)
    # スタッフ追加
    enable_add_staff = models.BooleanField(default=False)

    @receiver(post_save, sender=User)
    def create_permission(sender, instance, created, **kwargs):
        if created:
            Permission.objects.create(user=instance)

    @receiver(post_save, sender=User)
    def save_permission(sender, instance, **kwargs):
        if instance and instance.permission:
            instance.permission.save()


class Holiday(models.Model):
    """祝日"""

    date = models.DateField()

    def __str__(self):
        return "%s" % self.date


class WebTimeStamp(models.Model):
    """Web打刻"""

    employee = models.ForeignKey(
        "Employee", blank=True, null=True, on_delete=models.CASCADE
    )
    stamp = models.DateTimeField(blank=True, null=True)


class SteppingOut(models.Model):
    """ユーザーが外出した時間を記録する"""

    # Todo: dateフィールドを追加して、日付で管理できるようにする
    employee = models.ForeignKey(
        "Employee", blank=True, null=True, on_delete=models.CASCADE
    )
    out_time = models.DateTimeField(blank=True, null=True)
    return_time = models.DateTimeField(blank=True, null=True)

    def duration(self) -> datetime.timedelta:
        if self.out_time is None or self.return_time is None:
            return datetime.timedelta()
        return self.return_time - self.out_time


class DaySwitchTime(models.Model):
    """日付切替時間"""

    switch_time = models.TimeField(blank=True, null=True)


class EmployeeAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = (
        "employee_no",
        "name",
        "payed_holiday",
        "join_date",
        "leave_date",
        "user",
        "employee_type",
        "department",
    )


class WorkingHourAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = ("category", "begin_time", "end_time")


class TimeRecordAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = (
        "employee",
        "date",
        "clock_in",
        "clock_out",
        "status",
    )


class EmployeeHourAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = ("employee", "date", "working_hours")


class NotificationAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = ("employee", "category")


class ManagerAdmin(admin.ModelAdmin):
    """管理サイト"""

    pass


class PermissionAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = (
        "user",
        "enable_stamp_on_web",
        "enable_view_detail",
        "enable_view_dev_staff_record",
        "enable_view_outsource_staff_record",
    )


class WebStampAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = ("employee", "stamp")


class SteppingOutAdmin(admin.ModelAdmin):
    """管理サイト"""

    list_display = ("out_time", "return_time")


admin.site.register(Employee, EmployeeAdmin)
admin.site.register(WorkingHour, WorkingHourAdmin)
admin.site.register(EmployeeDailyRecord, TimeRecordAdmin)
admin.site.register(EmployeeHour, EmployeeHourAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Manager, ManagerAdmin)
admin.site.register(Permission, PermissionAdmin)
admin.site.register(WebTimeStamp, WebStampAdmin)
admin.site.register(SteppingOut, SteppingOutAdmin)


class Progress(models.Model):
    """進捗を表すモデル"""

    num = models.IntegerField("進捗", default=0)
    status = models.IntegerField("ステータス", default=0)
    message = models.CharField(max_length=128, null=True)

    def __str__(self):
        return self.num


class Foo(models.Model):
    """テストで使用するモデル"""

    pass


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
        null=True,
        blank=True,
    )
    # 対象日
    date = models.DateField(null=True, blank=True)
    # 調整後の時間
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateField(null=True, blank=True)
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


class OvertimePermission(models.Model):
    """時間外労働許可"""

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    # 許可された日付
    date = models.DateField()

    # 作成日
    created_at = models.DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return "%s %s %s" % (self.employee, self.date, self.created_at)


class FixedOvertimePayEmployee(models.Model):
    """固定残業の対象社員"""

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    # 固定残業時間（時間）
    hours = models.DurationField(default=datetime.timedelta(0))
    # 作成日
    created_at = models.DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return "%s %s" % (self.employee, self.hours)
