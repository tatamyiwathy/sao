from datetime import date, time, datetime, timedelta
from django.test import TestCase
from common.utils_for_test import create_user, create_employee
from sao.models import (
    EmployeeDailyRecord,
    SteppingOut,
    DaySwitchTime,
    Employee,
    WorkingHour,
    EmployeeDailyRecord,
    DailyAttendanceRecord,
    WebTimeStamp,
    OvertimePermission,
    FixedOvertimePayEmployee,
)
from sao.tests.utils import (
    create_working_hours,
    assign_working_hour,
    create_time_stamp_data,
    TOTAL_ACTUAL_WORKING_TIME,
    get_working_hour_by_category,
    create_timerecord,
)
from sao.utils import tally_over_work_time, tally_attendances
from sao.core import (
    adjust_working_hours,
    floor_to_30min,
    round_to_half_hour,
    round_attendance_summary,
    adjust_work_start_time,
    adjust_work_end_time,
    calc_actual_working_hours,
    calc_assumed_working_time,
    calc_tardiness,
    calc_leave_early,
    calc_overtime,
    calc_over_8h,
    calc_midnight_work,
    tally_steppingout,
    accumulate_weekly_working_hours,
    has_permitted_overtime_work,
    get_half_year_day,
    get_annual_paied_holiday_days,
    get_recent_day_of_annual_leave_update,
    is_need_break_time,
    get_monthy_time_record,
    get_employee_hour,
    get_working_hour_pre_assign,
    get_day_switch_time,
    normalize_to_attendance_day,
    get_clock_in_out,
    generate_daily_record,
    get_attendance_in_period,
    finalize_daily_record,
    get_monthly_attendance,
    permit_daily_overtime,
    has_permitted_daily_overtime,
    revoke_daily_overtime_permission,
    assign_fixed_overtime_pay,
    has_assigned_fixed_overtime_pay,
    remove_fixed_working_hours,
    generate_attendance_record,
    initiate_daily_attendance_record,
    adjust_stamp,
    assign_stamp_status,
    get_stepout_periods,
    fill_missing_attendance,
)
from sao.const import Const
from sao.calendar import (
    monthdays,
    is_holiday,
    get_next_month_date,
    get_last_sunday,
    get_next_sunday,
)
from sao.working_status import WorkingStatus
from django.test import TestCase
from unittest.mock import patch, MagicMock
from sao.period import Period
from sao.exceptions import NoAssignedWorkingHourError
from datetime import datetime, date, time, timedelta
from sao.core import update_attendance_record_and_save
from sao.models import DailyAttendanceRecord, Employee
from datetime import datetime, date, time
from sao.core import finalize_daily_record
from sao.models import (
    EmployeeDailyRecord,
    DailyAttendanceRecord,
    Employee,
    WebTimeStamp,
)


class AccumulateWeeklyWorkingHoursTest(TestCase):
    """"""

    def setUp(self) -> None:
        self.employee = create_employee(create_user())
        create_working_hours()

    def test_accumulate_weekly_working_hours(self) -> None:
        # 勤怠記録がある場合の週間勤務時間集計のテスト
        create_time_stamp_data(self.employee)
        records = get_monthly_attendance(self.employee, date(2021, 8, 1))
        results = accumulate_weekly_working_hours(records)
        week = 1
        for r in results:
            self.assertEqual(r[0], week)
            week += 1

    def test_accumulate_weekly_working_hours_when_empty(self) -> None:
        """勤怠記録がない場合の週間勤務時間集計のテスト"""
        # assign_working_hour(
        #     self.employee, date(1900, 1, 1), get_working_hour_by_category("A")
        # )

        d = date(2021, 8, 1)
        n = get_next_month_date(d)
        s0 = get_last_sunday(d)
        s1 = get_next_sunday(n)
        period = Period(
            datetime.combine(s0, time(0, 0)), datetime.combine(s1, time(0, 0))
        )

        attendances = get_monthly_attendance(self.employee, date(2021, 8, 1))
        attendances = fill_missing_attendance(self.employee, period, attendances)
        results = accumulate_weekly_working_hours(attendances)
        week = 1
        for r in results:
            self.assertEqual(r[0], week)
            week += 1


class TestRoundDown(TestCase):
    def test_round_down(self):
        t = timedelta(seconds=1700)
        self.assertEqual(floor_to_30min(t), timedelta(seconds=0))
        t = timedelta(seconds=1900)
        self.assertEqual(floor_to_30min(t), timedelta(minutes=30))


class TestRoundStamp(TestCase):
    def test_round_stamp(self):
        t = timedelta(seconds=13 * 3600 + 28 * 60)
        value = round_to_half_hour(t)
        self.assertEqual(value, timedelta(seconds=13 * 3600))

        t = timedelta(seconds=13 * 3600 + 35 * 60)
        value = round_to_half_hour(t)
        self.assertEqual(value, timedelta(seconds=14 * 3600))


class TestAdjustWorkStartTime(TestCase):
    def test_adjust_work_start_time(self):
        """打刻が勤務時間より早い場合、勤務時間の開始時刻に調整されること"""
        day = date(2021, 8, 2)
        clock_in = datetime.combine(day, time(9, 0))
        work_hours_start = datetime.combine(day, time(10, 0))
        starting_time = adjust_work_start_time(clock_in, work_hours_start)
        self.assertEqual(starting_time, work_hours_start)


class TestAdjustWorkEndTime(TestCase):
    def test_adjust_work_end_time_no_overtime_permission(self):
        """残業許可がないとき、打刻が勤務時間より遅い場合、勤務時間の終了時刻に調整されること"""
        d = date(2021, 8, 2)
        clock_out = datetime.combine(d, time(20, 0))
        work_hours_end = datetime.combine(d, time(19, 0))
        closing_time = adjust_work_end_time(clock_out, work_hours_end, False)
        self.assertEqual(closing_time, work_hours_end)

    def test_adjust_work_end_time_with_overtime_permission(self):
        """残業許可があるとき、打刻が勤務時間より遅い場合、打刻の時刻がそのまま終了時刻になること"""
        d = date(2021, 8, 2)
        clock_out = datetime.combine(d, time(20, 0))
        work_hours_end = datetime.combine(d, time(19, 0))
        closing_time = adjust_work_end_time(clock_out, work_hours_end, True)
        self.assertEqual(closing_time, clock_out)


class TestCalcActualWorkingHours(TestCase):

    def test_calc_actual_working_hours(self):
        """10-19の勤務時間から休息1時間を差し引いた8時間が実働時間になること"""
        d = date(2021, 8, 2)
        employee = create_employee(create_user())

        work_hours = Period(
            datetime.combine(d, time(10, 0)),
            datetime.combine(d, time(19, 0)),
        )

        actual_working_hours = calc_actual_working_hours(
            work_hours, WorkingStatus.C_KINMU, Const.TD_ZERO
        )
        self.assertEqual(actual_working_hours, timedelta(hours=8))

    def test_calc_actual_working_hours_less_6_hours(self):
        """6時間以下の勤務時間の場合、休息時間は発生しない"""
        d = date(2021, 8, 2)
        employee = create_employee(create_user())

        work_hours = Period(
            datetime.combine(d, time(10, 0)),
            datetime.combine(d, time(16, 0)),
        )
        actual_working_hours = calc_actual_working_hours(
            work_hours, WorkingStatus.C_KINMU, Const.TD_ZERO
        )
        self.assertEqual(actual_working_hours, timedelta(hours=6))


class TestCalcTardy(TestCase):
    def test_calc_tardy(self):
        d = date(2021, 8, 2)

        clock_in = datetime.combine(d, time(10, 15))
        work_hours_start = datetime.combine(d, time(10, 0))
        tardy = calc_tardiness(clock_in, work_hours_start)
        self.assertEqual(tardy, timedelta(minutes=15))

    def test_calc_no_tardy(self):
        d = date(2021, 8, 2)

        clock_in = datetime.combine(d, time(9, 52))
        work_hours_start = datetime.combine(d, time(10, 0))
        tardy = calc_tardiness(clock_in, work_hours_start)
        self.assertEqual(tardy, Const.TD_ZERO)

    def test_calc_tardy_if_no_clock_in(self):
        d = date(2021, 8, 2)

        clock_in = datetime.combine(d, time(10, 0))
        work_hours_start = datetime.combine(d, time(10, 0))
        with self.assertRaises(TypeError):
            calc_tardiness(None, work_hours_start)


class TestCalcLeaveEarly(TestCase):
    def test_calc_leave_early(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user())

        clock_out = datetime.combine(d, time(18, 0))
        work_hours_end = datetime.combine(d, time(19, 0))
        leave_early_time = calc_leave_early(clock_out, work_hours_end)
        self.assertEqual(leave_early_time, timedelta(minutes=60))

    def test_calc_no_leave_early(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user())

        clock_out = datetime.combine(d, time(19, 0))
        work_hours_end = datetime.combine(d, time(19, 0))
        leave_early_time = calc_leave_early(clock_out, work_hours_end)
        self.assertEqual(leave_early_time, Const.TD_ZERO)

    def test_calc_leave_early_if_no_clock_out(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user())

        work_hours_end = datetime.combine(d, time(19, 0))

        with self.assertRaises(TypeError):
            leave_early_time = calc_leave_early(None, work_hours_end)


class TestTallySteppingOut(TestCase):
    """外出時間を集計するテスト"""

    def test_tally_steppingout(self):
        employee = create_employee(create_user())
        SteppingOut(
            employee=employee,
            out_time=datetime(2021, 8, 2, 13, 0, 0),
            return_time=datetime(2021, 8, 2, 14, 0, 0),
        ).save()
        total_stepping_out = tally_steppingout(
            employee, datetime(2021, 8, 2, 9, 0), datetime(2021, 8, 2, 18, 0)
        )
        self.assertEqual(total_stepping_out, Const.TD_1H)

    def test_tally_steppingout_when_empty(self):
        employee = create_employee(create_user())

        total_stepping_out = tally_steppingout(employee, None, None)
        self.assertEqual(total_stepping_out, Const.TD_ZERO)


class TestCalcOvertime(TestCase):
    """超過勤務時間を計算するテスト
    - このテストでは休息時間を考慮しない
    """

    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    def test_overtime_not_permitted(self):
        """残業許可がないときは時間外の打刻でも超過時間は発生しない"""
        d = date(2021, 8, 3)
        actual_work = Period(
            datetime.combine(d, time(hour=10)), datetime.combine(d, time(hour=21))
        )
        work_period = Period(
            datetime.combine(d, time(10, 0)),
            datetime.combine(d, time(19, 0)),
        )
        over = calc_overtime(actual_work.duration(), work_period.duration(), False)
        self.assertEqual(over, Const.TD_ZERO)

    def test_overtime_permitted(self):
        """残業許可があるときは残業時間が発生する"""

        scheduled_start = datetime(2021, 8, 3, 10, 0, 0)
        scheduled_end = datetime(2021, 8, 3, 19, 0, 0)
        scheduled_duration = scheduled_end - scheduled_start

        actual_start = datetime(2021, 8, 3, 10, 00, 0)
        actual_end = datetime(2021, 8, 3, 20, 0, 0)  # 1時間残業
        actual_duration = actual_end - actual_start

        overtime = calc_overtime(actual_duration, scheduled_duration, True)
        self.assertEqual(overtime, timedelta(hours=1))

    def test_calc_overtime_if_tardy(self):
        """遅刻して残業したとしても所定の勤務時間を満たしていなければ超過にならない"""
        scheduled_start = datetime(2021, 8, 2, 10, 0, 0)
        scheduled_end = datetime(2021, 8, 2, 19, 0, 0)
        scheduled_duration = scheduled_end - scheduled_start

        actual_start = datetime(2021, 8, 2, 13, 00, 0)
        actual_end = datetime(2021, 8, 2, 20, 0, 0)  # 1時間残業
        actual_duration = actual_end - actual_start

        overtime = calc_overtime(actual_duration, scheduled_duration, True)
        # 所定勤務時間より１時間オーバーしてるけど実働勤務が７時間なので超過勤務にはならない
        self.assertEqual(overtime, timedelta(hours=0))

    def test_calc_overtime_when_holiday(self):
        """休日出勤の場合は超過時間は発生しない"""
        actual_start = datetime(2021, 8, 1, 11, 00, 0)
        actual_end = datetime(2021, 8, 1, 15, 00, 0)
        actual_duration = actual_end - actual_start

        # 休出は所定の勤務時間がないので実働時間をそのまま所定勤務時間とする
        scheduled_start = actual_start
        scheduled_hours_end = actual_end
        scheduled_duration = scheduled_hours_end - scheduled_start

        overtime = calc_overtime(actual_duration, scheduled_duration, True)
        """休日出勤なので残業がない"""
        self.assertEqual(overtime, timedelta(hours=0))

    def test_when_absent(self):
        """欠勤の場合、超過勤務は発生しない"""
        scheduled_start = None
        scheduled_hours_end = None
        scheduled_duration = timedelta(0)

        actual_start = None
        actual_end = None
        actual_duration = timedelta(0)

        overtime = calc_overtime(actual_duration, scheduled_duration, True)
        # 欠勤なので0になる
        self.assertEqual(overtime, timedelta(hours=0))


class TestCalcOver8h(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    def test_calc_over_8h_if_overtime_not_permitted(self):
        """残業が許可されていない場合、超過時間が発生しない"""
        actual_hours = Const.TD_9H  # 1時間残業

        over_8h = calc_over_8h(actual_hours, False)
        self.assertEqual(over_8h, timedelta(hours=0))

    def test_calc_over_8h_if_overtime_permitted(self):
        """残業が許可されている場合、超過時間が発生する"""
        actual_hours = Const.TD_9H  # 1時間残業

        over_8h = calc_over_8h(actual_hours, True)
        self.assertEqual(over_8h, Const.TD_1H)

    def test_calc_over_8h_missed_stamp(self):
        """打刻がないので0とする"""
        actual_duration = Const.TD_ZERO  # 打刻がない場合、実働時間は０

        over_8h = calc_over_8h(actual_duration, True)
        self.assertEqual(over_8h, timedelta(hours=0))


class TestCalcMidnightWork(TestCase):
    """深夜勤務(割り増し)時間を計算するテスト
    - 割り増しは深夜時刻を超過したら法定休日、法定外休日問わず発生する
    """

    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    def test_calc_midnight_work_before_midnight(self):
        """22時前に退勤した場合、深夜勤務時間は0とする"""
        midnight_work = calc_midnight_work(datetime(2021, 8, 3, 21, 51, 0))
        self.assertEqual(midnight_work, timedelta(minutes=0))

    def test_calc_midnight_work_at_midnight(self):
        """22時超過した場合、深夜勤務時間を計算する"""
        midnight_work = calc_midnight_work(datetime(2021, 8, 3, 22, 15, 0))
        self.assertEqual(midnight_work, timedelta(minutes=15))


class TestIsPermitOvertime(TestCase):
    def test_has_permitted_overtime(self):
        """固定残業時間が設定されている場合、残業が許可されることを確認する"""
        employee = create_employee(create_user())
        assign_fixed_overtime_pay(employee, Const.FIXED_OVERTIME_HOURS_20)
        permit_overtime = has_permitted_overtime_work(employee, None)
        self.assertTrue(permit_overtime)

    def test_has_not_overtime_permittion(self):
        """固定残業時間が設定されていない場合、残業が許可されないことを確認する"""
        employee = create_employee(create_user())
        permit_overtime = has_permitted_overtime_work(employee, None)
        self.assertFalse(permit_overtime)


class TestGetAnnualPaidHolidayDays(TestCase):
    def test_get_annual_paied_holiday_days(self):
        join_date = date(2021, 1, 1)

        # 3か月後
        annual_leave_update_date = date(2021, 3, 1)
        annual_paid_holiday_days = get_annual_paied_holiday_days(
            annual_leave_update_date, join_date
        )
        self.assertEqual(annual_paid_holiday_days, 0)

        # 6か月後 -1日
        annual_leave_update_date = date(2021, 6, 30)
        annual_paid_holiday_days = get_annual_paied_holiday_days(
            annual_leave_update_date, join_date
        )
        self.assertEqual(annual_paid_holiday_days, 0)

        # 6か月後
        annual_leave_update_date = date(2021, 7, 1)
        annual_paid_holiday_days = get_annual_paied_holiday_days(
            annual_leave_update_date, join_date
        )
        self.assertEqual(annual_paid_holiday_days, 10)

    def test_when_specify_anomaly_date(self):
        join_date = date(2021, 3, 1)
        annual_leave_update_date = date(2021, 1, 1)
        with self.assertRaises(ValueError):
            get_annual_paied_holiday_days(annual_leave_update_date, join_date)


class TestGetRecentDayOfAnnualLeaveUpdate(TestCase):
    """年次有給休暇付与日の直近日を取得するテスト"""

    def test_get_recent_day_of_annual_leave_update(self):
        """更新日は最初の年は入社日の半年後"""
        join_date = datetime(2021, 1, 1, 0, 0, 0)
        update_day = get_recent_day_of_annual_leave_update(2021, join_date)
        self.assertEqual(update_day, date(2021, 7, 1))

    def test_alter_year(self):
        """2年目以降は1年目の更新日の1年後"""
        join_date = date(2021, 1, 1)
        update_day = get_recent_day_of_annual_leave_update(2022, join_date)
        self.assertEqual(update_day, date(2022, 7, 1))

    def test_get_recent_day_of_annual_leave_update_when_leap_year(self):
        """うるう年の入社日の場合、半年後の日付を正しく取得できること"""
        join_date = date(2020, 2, 29)
        update_day = get_recent_day_of_annual_leave_update(2020, join_date)
        self.assertEqual(update_day, date(2020, 8, 29))

    def test_get_annual_leave_update_day_included_leap_day(self):
        """うるう日をまたぐ半年後の日付を正しく取得できること"""
        join_date = date(2024, 1, 1)
        update_day = get_recent_day_of_annual_leave_update(2024, join_date)
        # 閏日があろうと半年後は7月1日
        self.assertEqual(update_day, date(2024, 7, 1))


class TestIsNeedBreakTime(TestCase):
    """休息時間が必要かどうかを判定するテスト"""

    def test_need_break_time(self):
        # 6時間超労働で休息が必要
        work = timedelta(hours=8)
        status = WorkingStatus.C_KINMU
        need_break_time = is_need_break_time(work, status)
        self.assertTrue(need_break_time)

    def test_no_need_break_time_just_6_hours(self):
        # 勤務時間が6時間ちょうどの場合、休息は不要
        work_period = timedelta(hours=6)
        status = WorkingStatus.C_KINMU
        need_break_time = is_need_break_time(work_period, status)
        self.assertFalse(need_break_time)

    def test_no_need_break_time_afternoon_off(self):
        # 午後休で休息は不要
        work_period = timedelta(hours=5)
        status = WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI
        need_break_time = is_need_break_time(work_period, status)
        self.assertFalse(need_break_time)

    def test_when_alternoon_off_with_rest(self):
        # 午後休で休息が必要
        work_period = timedelta(hours=5)
        status = WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI
        need_break_time = is_need_break_time(work_period, status)
        self.assertTrue(need_break_time)


class TestGetMonthlyTimeRecord(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    """月の勤怠記録を収集するテスト"""

    def test_get_monthy_time_record(self):
        create_time_stamp_data(self.employee)  # 打刻データ生成

        records = get_monthy_time_record(self.employee, date(2021, 8, 1))
        self.assertEqual(len(records), monthdays(date(2021, 8, 1)))

    def test_get_empty_monthy_time_record(self):
        """勤怠記録がない場合、空の勤怠記録を生成すること"""
        records = get_monthy_time_record(self.employee, date(2021, 9, 1))
        self.assertTrue(all(r.status == WorkingStatus.C_NONE for r in records))


class TestGetEmplyeeHour(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user())
        create_working_hours()

    def test_get_employee_hour(self):
        assign_working_hour(
            self.employee, date(1901, 1, 1), get_working_hour_by_category("A")
        )

        office_hours = get_employee_hour(self.employee, date(2021, 8, 1))
        self.assertEqual(office_hours.begin_time, Const.OCLOCK_1000)
        self.assertEqual(office_hours.end_time, Const.OCLOCK_1900)

    def test_get_employee_hour_when_not_set(self):
        # 勤務時間が設定されていない場合、例外を送出すること
        with self.assertRaises(NoAssignedWorkingHourError):
            get_employee_hour(self.employee, date(2021, 8, 1))


class TestGetWorkingHoursByCategory(TestCase):
    def test_get_working_hours_by_category(self):
        create_working_hours()
        working_hours = get_working_hour_by_category("A")
        self.assertEqual(working_hours.begin_time, Const.OCLOCK_1000)
        self.assertEqual(working_hours.end_time, Const.OCLOCK_1900)

    def test_get_category_not_found(self):
        with self.assertRaises(WorkingHour.DoesNotExist):
            get_working_hour_by_category("Z")


class TestGetWorkingHoursToBeAssign(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    def test_get_working_hours_pre_assign(self):
        create_working_hours()
        assign_working_hour(
            self.employee, date(1901, 1, 1), get_working_hour_by_category("A")
        )
        working_hours = get_working_hour_pre_assign(self.employee).working_hours
        self.assertEqual(working_hours.begin_time, Const.OCLOCK_1000)
        self.assertEqual(working_hours.end_time, Const.OCLOCK_1900)


class TestGetDaySwitchTime(TestCase):
    def test_get_day_switch_time(self):
        # Arrange: create a DaySwitchTime object in the database
        DaySwitchTime.objects.all().delete()
        DaySwitchTime.objects.create(switch_time=time(5, 0))

        # Act
        result = get_day_switch_time()

        # Assert
        self.assertEqual(result, time(5, 0))

    def test_get_day_switch_time_none(self):
        # Arrange: ensure no DaySwitchTime objects exist
        DaySwitchTime.objects.all().delete()

        # Act & Assert: should raise AttributeError if .first() returns None
        self.assertEqual(get_day_switch_time(), time(5, 0))


class TestNormalizeToBusinessDay(TestCase):
    def setUp(self):
        DaySwitchTime.objects.all().delete()
        DaySwitchTime.objects.create(switch_time=time(5, 0))

    def test_normalize_to_business_day_before_switch_time(self):
        # 4:30 AM, should normalize to previous day
        dt = datetime(2021, 8, 2, 4, 30)
        normalized = normalize_to_attendance_day(dt)
        self.assertEqual(normalized, datetime(2021, 8, 1, 4, 30))

    def test_normalize_to_business_day_at_switch_time(self):
        # 5:00 AM, should not normalize
        dt = datetime(2021, 8, 2, 5, 0)
        normalized = normalize_to_attendance_day(dt)
        self.assertEqual(normalized, dt)

    def test_normalize_to_business_day_after_switch_time(self):
        # 6:00 AM, should not normalize
        dt = datetime(2021, 8, 2, 6, 0)
        normalized = normalize_to_attendance_day(dt)
        self.assertEqual(normalized, dt)


class TestAdjustWorkingHours(TestCase):
    def setUp(self):
        # Minimal Employee mock
        self.employee = Employee(name="Test Employee")
        # Standard working hours: 10:00-19:00
        self.day = date(2023, 8, 2)
        self.working_hour = Period(
            datetime.combine(self.day, Const.OCLOCK_1000),
            datetime.combine(self.day, Const.OCLOCK_1900),
        )

    def test_normal_workday(self):
        # 平日、出勤退勤あり

        working_hours = adjust_working_hours(self.working_hour, WorkingStatus.C_KINMU)
        self.assertEqual(
            working_hours.start, datetime.combine(self.day, Const.OCLOCK_1000)
        )
        self.assertEqual(
            working_hours.end, datetime.combine(self.day, Const.OCLOCK_1900)
        )

    def test_holiday_work(self):
        """
        休日出勤、出勤退勤あり->打刻そのまま
        """

        # 休出のときは所定の勤務時間がないので打刻時間をそのまま使う
        work_hours = Period(
            datetime.combine(self.day, time(11, 30)),
            datetime.combine(self.day, time(18, 0)),
        )
        working_hours = adjust_working_hours(work_hours, WorkingStatus.C_KINMU)
        self.assertEqual(working_hours.start, datetime.combine(self.day, time(11, 30)))
        self.assertEqual(working_hours.end, datetime.combine(self.day, time(18, 0)))

    def test_morning_off(self):
        """午前休（休息あり）"""
        working_hours = adjust_working_hours(
            self.working_hour, WorkingStatus.C_YUUKYUU_GOZENKYU
        )
        # Duration = 9h, minus 1h rest = 8h, half = 4h
        expected_start = (
            datetime.combine(self.day, Const.OCLOCK_1000)
            + timedelta(hours=4)
            + Const.TD_1H
        )
        expected_end = datetime.combine(self.day, Const.OCLOCK_1900)
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    def test_afternoon_off_with_rest(self):
        # 午後休（休息あり）
        working_hours = adjust_working_hours(
            self.working_hour, WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI
        )
        # Duration = 9h, minus 1h rest = 8h, half = 4h
        expected_start = datetime.combine(self.day, Const.OCLOCK_1000)
        expected_end = datetime.combine(self.day, Const.OCLOCK_1900) - timedelta(
            hours=4
        )
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    def test_afternoon_off_no_rest(self):
        # 午後休（休息なし）
        working_hours = adjust_working_hours(
            self.working_hour, WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI
        )
        # Duration = 9h, minus 1h rest = 8h, half = 4h, minus 1h rest
        expected_start = datetime.combine(self.day, Const.OCLOCK_1000)
        expected_end = (
            datetime.combine(self.day, Const.OCLOCK_1900)
            - timedelta(hours=4)
            - Const.TD_1H
        )
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    def test_short_working_hours_no_rest(self):
        # 勤務時間が６時間以下、休息なし
        # Working hour less than 6h, no rest adjustment
        short_working_hour = Period(
            datetime.combine(self.day, time(10, 0)),
            datetime.combine(self.day, time(15, 0)),
        )

        working_hours = adjust_working_hours(short_working_hour, WorkingStatus.C_KINMU)
        self.assertEqual(working_hours.start, datetime.combine(self.day, time(10, 0)))
        self.assertEqual(working_hours.end, datetime.combine(self.day, time(15, 0)))


class TestGetClockInOut(TestCase):
    def setUp(self):
        # Import Period from the correct location
        self.Period = Period
        self.dt = datetime(2023, 8, 2, 9, 0, 0)
        self.dt2 = datetime(2023, 8, 2, 18, 0, 0)
        self.dt3 = datetime(2023, 8, 2, 20, 0, 0)

    def test_no_stamps(self):
        result = get_clock_in_out([])
        self.assertIsInstance(result, self.Period)
        self.assertIsNone(result.start)
        self.assertIsNone(result.end)

    def test_one_stamp(self):
        result = get_clock_in_out([self.dt])
        self.assertIsInstance(result, self.Period)
        self.assertEqual(result.start, self.dt)
        self.assertIsNone(result.end)

    def test_two_stamps(self):
        result = get_clock_in_out([self.dt, self.dt2])
        self.assertIsInstance(result, self.Period)
        self.assertEqual(result.start, self.dt)
        self.assertEqual(result.end, self.dt2)

    def test_multiple_stamps(self):
        result = get_clock_in_out([self.dt, self.dt2, self.dt3])
        self.assertIsInstance(result, self.Period)
        self.assertEqual(result.start, self.dt)
        self.assertEqual(result.end, self.dt3)


class TestGenerateDailyRecord(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user())
        create_working_hours()
        assign_working_hour(
            self.employee, date(1901, 1, 1), get_working_hour_by_category("A")
        )
        return super().setUp()

    def test_generate(self):
        stamps = [datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)]
        day = date(2023, 8, 2)
        generate_daily_record(stamps, self.employee, day)
        self.assertTrue(EmployeeDailyRecord.objects.all().count() == 1)

    def test_no_stamps(self):
        stamps = []
        day = date(2023, 8, 2)
        generate_daily_record(stamps, self.employee, day)
        self.assertTrue(EmployeeDailyRecord.objects.all().count() == 1)

    @patch("sao.core.get_employee_hour")
    def test_no_working_hour_assigned(self, mock_get_employee_hour):
        mock_get_employee_hour.side_effect = NoAssignedWorkingHourError(
            "勤務時間が設定されていません"
        )

        stamps = [datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)]
        day = date(2023, 8, 2)

        # テスト実行
        result = generate_daily_record(stamps, self.employee, day)

        # 例外が発生してNoneが返されることを確認
        self.assertIsNone(result)


class TestOvertimePermission(TestCase):
    """時間外労働の許可設定を確認するテスト"""

    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    @patch("sao.core.has_permitted_overtime_work", return_value=False)
    def test_permit_overtime(self, mock_has_permitted_overtime_work):
        permit_daily_overtime(self.employee, date(2021, 8, 1))
        self.assertTrue(
            OvertimePermission.objects.filter(
                employee=self.employee, date=date(2021, 8, 1)
            ).exists()
        )

    @patch("sao.models.OvertimePermission.objects.create")
    @patch("sao.core.has_permitted_overtime_work", return_value=True)
    def test_permit_overtime_if_not_exists(
        self, mock_has_permitted_overtime_work, mock_create
    ):
        """既に許可されている場合、再度許可しても重複しないこと"""
        permit_daily_overtime(self.employee, date(2021, 8, 1))
        mock_create.assert_not_called()

    def test_oertime_permission_exists(self):
        """時間外労働が許可されているかどうかを確認するテスト"""
        OvertimePermission.objects.create(employee=self.employee, date=date(2021, 8, 1))
        self.assertTrue(has_permitted_daily_overtime(self.employee, date(2021, 8, 1)))

    def test_revoke_overtime(self):
        """時間外労働の許可を取り消すテスト"""
        OvertimePermission.objects.create(employee=self.employee, date=date(2021, 8, 1))
        revoke_daily_overtime_permission(self.employee, date(2021, 8, 1))
        self.assertFalse(
            OvertimePermission.objects.filter(
                employee=self.employee, date=date(2021, 8, 1)
            ).exists()
        )


class TestFixedOvertimePay(TestCase):
    """固定残業代の確認テスト"""

    def setUp(self) -> None:
        self.employee = create_employee(create_user())

    def test_assign_employee_fixed_overtime_pay(self):
        """固定残業代を従業員に割り当てるテスト"""
        assign_fixed_overtime_pay(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        self.assertTrue(
            FixedOvertimePayEmployee.objects.filter(employee=self.employee).exists()
        )

    def test_invoke_assign_fixed_overtime_pay_twice(self):
        """固定残業代を2回割り当てても重複しないこと"""
        assign_fixed_overtime_pay(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        assign_fixed_overtime_pay(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        self.assertEqual(
            FixedOvertimePayEmployee.objects.filter(employee=self.employee).count(), 1
        )

    def test_is_assigned_fixed_overtime_pay(self):
        """従業員に固定残業代が割り当てられているかどうかを確認するテスト"""
        assign_fixed_overtime_pay(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        self.assertTrue(has_assigned_fixed_overtime_pay(self.employee))

    def test_revoke_fixed_overtime_pay(self):
        """従業員の固定残業代を取り消すテスト"""
        assign_fixed_overtime_pay(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        remove_fixed_working_hours(self.employee, Const.FIXED_OVERTIME_HOURS_20)
        self.assertFalse(has_assigned_fixed_overtime_pay(self.employee))


class TestGenerateDailyAttendanceRecord(TestCase):
    def setUp(self):
        self.employee = create_employee(create_user())
        self.day = date(2023, 8, 2)
        self.record = EmployeeDailyRecord.objects.create(
            date=self.day,
            employee=self.employee,
            clock_in=datetime.combine(self.day, time(10, 0)),
            clock_out=datetime.combine(self.day, time(19, 0)),
            working_hours_start=datetime.combine(self.day, time(10, 0)),
            working_hours_end=datetime.combine(self.day, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )

    def test_generate_attendance_record(self):
        # 正常に勤怠記録が生成されること
        generate_attendance_record(self.record)
        attendance_record = DailyAttendanceRecord.objects.filter(
            employee=self.employee, date=self.day
        ).first()
        self.assertIsNotNone(attendance_record)
        if attendance_record is not None:
            self.assertEqual(attendance_record.clock_in, self.record.clock_in)
            self.assertEqual(attendance_record.clock_out, self.record.clock_out)
            self.assertEqual(
                attendance_record.working_hours_start, self.record.working_hours_start
            )
            self.assertEqual(
                attendance_record.working_hours_end, self.record.working_hours_end
            )
            self.assertEqual(attendance_record.status, self.record.status)

    def test_generate_attendance_if_stamp_empty(self):
        # 打刻がない場合でも勤怠記録が生成されること
        self.record.clock_in = None
        self.record.clock_out = None
        attendance = generate_attendance_record(self.record)
        self.assertIsNotNone(attendance)


class TestAdjustStamp(TestCase):
    def setUp(self):
        self.day = date(2023, 8, 2)

    def test_adjust_stamp(self):
        work_hours = Period(
            datetime.combine(self.day, time(10, 0)),
            datetime.combine(self.day, time(19, 0)),
        )
        actual_work = Period(
            datetime.combine(self.day, time(9, 50)),
            datetime.combine(self.day, time(20, 0)),
        )

        adjusted = adjust_stamp(actual_work, work_hours, False)
        self.assertEqual(adjusted.start, datetime.combine(self.day, time(10, 0)))
        self.assertEqual(adjusted.end, datetime.combine(self.day, time(19, 0)))

    def test_adjust_stamp_overtime_permitted(self):
        work_hours = Period(
            datetime.combine(self.day, time(10, 0)),
            datetime.combine(self.day, time(19, 0)),
        )
        actual_work = Period(
            datetime.combine(self.day, time(9, 50)),
            datetime.combine(self.day, time(20, 0)),
        )

        adjusted = adjust_stamp(actual_work, work_hours, True)
        self.assertEqual(adjusted.start, datetime.combine(self.day, time(10, 0)))
        self.assertNotEqual(adjusted.end, datetime.combine(self.day, time(19, 0)))

    def test_adjust_stamp_no_stamp(self):
        """打刻がない場合、Noneのままであること
        - 欠勤
        """
        work_hours = Period(
            datetime.combine(self.day, time(10, 0)),
            datetime.combine(self.day, time(19, 0)),
        )
        actual_work = Period(None, None)

        adjusted = adjust_stamp(actual_work, work_hours, False)
        self.assertIsNone(adjusted.start)
        self.assertIsNone(adjusted.end)

    def test_adjust_stamp_no_working_hours(self):
        """所定労働時間がない場合、打刻をそのまま返すこと
        - 休日出勤など
        """
        work_hours = Period(None, None)
        actual_work = Period(None, None)

        adjusted = adjust_stamp(actual_work, work_hours, False)
        self.assertIsNone(adjusted.start)
        self.assertIsNone(adjusted.end)


class AssignStampStatusTest(TestCase):
    def setUp(self):
        self.working_hours = Period(
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 19, 0),
        )

    def test_assign_stamp_status(self):
        # 打刻が両方ある場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 19, 0),
        ]

        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[0][1], 1)  # 出勤
        self.assertEqual(stamps[1][1], 4)  # 退勤

        stamps = [
            datetime(2023, 8, 2, 10, 0),
        ]
        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[0][1], 1)  # 出勤

        stamps = [
            datetime(2023, 8, 2, 19, 0),
        ]
        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[0][1], 4)  # 退勤

    def test_when_stepping_out(self):
        # 外出、戻りの打刻がある場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 12, 0),
            datetime(2023, 8, 2, 13, 0),
            datetime(2023, 8, 2, 19, 0),
        ]

        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[0][1], 1)  # 出勤
        self.assertEqual(stamps[1][1], 2)  # 外出
        self.assertEqual(stamps[2][1], 3)  # 戻り
        self.assertEqual(stamps[3][1], 4)  # 退勤

    def test_when_stepping_out_any_times(self):
        # 外出、戻りの打刻がある場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 12, 0),
            datetime(2023, 8, 2, 13, 0),
            datetime(2023, 8, 2, 14, 0),
            datetime(2023, 8, 2, 15, 0),
            datetime(2023, 8, 2, 19, 0),
        ]

        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[0][1], 1)  # 出勤
        self.assertEqual(stamps[1][1], 2)  # 外出
        self.assertEqual(stamps[2][1], 3)  # 戻り
        self.assertEqual(stamps[3][1], 2)  # 外出
        self.assertEqual(stamps[4][1], 3)  # 戻り
        self.assertEqual(stamps[5][1], 4)  # 退勤

    def test_when_missed_return_stamp(self):
        # 戻りの打刻がない場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 15, 0),
            datetime(2023, 8, 2, 19, 0),
        ]

        stamps = assign_stamp_status(stamps, self.working_hours)
        self.assertEqual(stamps[2][1], 4)  # 退勤


class GetStepoutPeriodTest(TestCase):
    def setUp(self):
        self.working_hours = Period(
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 19, 0),
        )

    def test_get_stepout_period_empty(self):
        # 打刻がない場合
        stamps = []
        stepout_period = get_stepout_periods(stamps, self.working_hours)
        self.assertEqual(len(stepout_period), 0)

    def test_get_stepout_period(self):
        # 外出、戻りの打刻がある場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),
            datetime(2023, 8, 2, 12, 0),
            datetime(2023, 8, 2, 13, 0),
            datetime(2023, 8, 2, 14, 0),
            datetime(2023, 8, 2, 15, 0),
            datetime(2023, 8, 2, 19, 0),
        ]

        stepout_period = get_stepout_periods(stamps, self.working_hours)
        self.assertEqual(len(stepout_period), 2)
        self.assertEqual(stepout_period[0].start, datetime(2023, 8, 2, 12, 0))
        self.assertEqual(stepout_period[0].end, datetime(2023, 8, 2, 13, 0))
        self.assertEqual(stepout_period[1].start, datetime(2023, 8, 2, 14, 0))
        self.assertEqual(stepout_period[1].end, datetime(2023, 8, 2, 15, 0))

    def test_get_stepout_period_no_stepout(self):
        # 外出、戻りの打刻がない場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),  # 出勤
            datetime(2023, 8, 2, 19, 0),  # 退勤
        ]

        stepout_period = get_stepout_periods(stamps, self.working_hours)
        self.assertEqual(len(stepout_period), 0)

    def test_get_stepout_period_incomplete(self):
        # 外出、戻りの打刻がない場合
        stamps = [
            datetime(2023, 8, 2, 10, 0),  # 出勤
            datetime(2023, 8, 2, 12, 0),  # 外出
            datetime(2023, 8, 2, 19, 0),  # 退勤
        ]
        stepout_period = get_stepout_periods(stamps, self.working_hours)
        self.assertEqual(len(stepout_period), 1)
        print("################ %s" % stepout_period[0])


class TestInitiateDailyAttendanceRecord(TestCase):
    def setUp(self):
        self.employee = create_employee(create_user())
        self.day = date(2023, 8, 2)
        self.record = EmployeeDailyRecord.objects.create(
            date=self.day,
            employee=self.employee,
            clock_in=datetime.combine(self.day, time(10, 0)),
            clock_out=datetime.combine(self.day, time(19, 0)),
            working_hours_start=datetime.combine(self.day, time(10, 0)),
            working_hours_end=datetime.combine(self.day, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )
        self.attendance = DailyAttendanceRecord.objects.create(
            time_record=self.record,
            employee=self.employee,
            date=self.day,
            clock_in=datetime.combine(self.day, time(10, 0)),
            clock_out=datetime.combine(self.day, time(19, 0)),
            working_hours_start=datetime.combine(self.day, time(10, 0)),
            working_hours_end=datetime.combine(self.day, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )

    def test_return_if_missing_working_hours(self):
        self.attendance.working_hours_start = None
        result = initiate_daily_attendance_record(self.attendance)
        self.assertEqual(result, self.attendance)

        self.attendance.working_hours_start = datetime.combine(self.day, time(10, 0))
        self.attendance.working_hours_end = None
        result = initiate_daily_attendance_record(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_missing_date(self):
        self.attendance.date = None
        result = initiate_daily_attendance_record(self.attendance)
        self.assertEqual(result, self.attendance)

    @patch("sao.core.has_permitted_overtime_work", return_value=True)
    def test_overtime_permission_sets_flag(self, mock_has_permitted_overtime_work):
        self.attendance.overtime_permitted = False
        result = initiate_daily_attendance_record(self.attendance)
        self.assertTrue(result.overtime_permitted)

    @patch("sao.core.calendar_is_holiday", return_value=True)
    def test_holiday_sets_working_hours_to_stamp(self, mock_calendar_is_holiday):
        self.attendance.clock_in = datetime.combine(self.day, time(11, 0))
        self.attendance.clock_out = datetime.combine(self.day, time(18, 0))
        result = initiate_daily_attendance_record(self.attendance)
        self.assertEqual(result.working_hours_start, self.attendance.clock_in)
        self.assertEqual(result.working_hours_end, self.attendance.clock_out)

    @patch("sao.core.adjust_stamp")
    @patch("sao.core.calendar_is_holiday", return_value=False)
    def test_adjust_stamp_called_when_not_holiday(
        self, mock_calendar_is_holiday, mock_adjust_stamp
    ):
        mock_adjust_stamp.return_value = Period(
            datetime.combine(self.day, time(10, 5)),
            datetime.combine(self.day, time(18, 55)),
        )
        result = initiate_daily_attendance_record(self.attendance)
        self.assertEqual(result.clock_in, datetime.combine(self.day, time(10, 5)))
        self.assertEqual(result.clock_out, datetime.combine(self.day, time(18, 55)))


class TestUpdateAttendanceRecordAndSave(TestCase):
    def setUp(self):
        self.employee = create_employee(create_user())
        self.day = date(2023, 8, 2)
        self.record = create_timerecord(
            employee=self.employee,
            date=self.day,
            stamp=[
                datetime.combine(self.day, time(10, 0)),
                datetime.combine(self.day, time(20, 0)),
            ],
            working_hours=(
                datetime.combine(self.day, time(10, 0)),
                datetime.combine(self.day, time(19, 0)),
            ),
            status=WorkingStatus.C_KINMU,
        )

        self.attendance = DailyAttendanceRecord.objects.create(
            employee=self.employee,
            time_record=self.record,
            date=self.day,
            clock_in=self.record.clock_in,
            clock_out=self.record.clock_out,
            working_hours_start=self.record.working_hours_start,
            working_hours_end=self.record.working_hours_end,
            status=self.record.status,
        )

    def test_return_if_missing_clock_in_or_out(self):
        # 打刻が片方欠けている場合、処理をスキップすること
        self.attendance.clock_in = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)
        self.attendance.clock_in = datetime.combine(self.day, time(10, 0))
        self.attendance.clock_out = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_missing_working_hours(self):
        # 所定労働時間が片方欠けている場合、処理をスキップすること
        self.attendance.working_hours_start = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)
        self.attendance.working_hours_start = datetime.combine(self.day, time(10, 0))
        self.attendance.working_hours_end = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_missing_date(self):
        # 日付が欠けている場合、処理をスキップすること
        self.attendance.date = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_missing_status(self):
        self.attendance.status = WorkingStatus.C_NONE
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_stamp_missing(self):
        # 打刻が両方欠けている場合、処理をスキップすること
        self.attendance.clock_in = None
        self.attendance.clock_out = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    def test_return_if_work_hours_missing(self):
        # 所定労働時間が両方欠けている場合、処理をスキップすること
        self.attendance.working_hours_start = None
        self.attendance.working_hours_end = None
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result, self.attendance)

    @patch("sao.core.calc_actual_working_hours", return_value=timedelta(hours=8))
    @patch("sao.core.calc_tardiness", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_leave_early", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_overtime", return_value=timedelta(hours=1))
    @patch("sao.core.calc_over_8h", return_value=timedelta(hours=1))
    @patch("sao.core.calc_midnight_work", return_value=timedelta(minutes=0))
    @patch("sao.core.has_permitted_overtime_work", return_value=True)
    @patch("sao.core.calendar_is_holiday", return_value=False)
    @patch("sao.core.is_legal_holiday", return_value=False)
    def test_update_attendance_record_and_save_sets_fields(
        self,
        mock_is_legal_holiday,
        mock_calendar_is_holiday,
        mock_has_permitted_overtime_work,
        mock_calc_midnight_work,
        mock_calc_over_8h,
        mock_calc_overtime,
        mock_calc_leave_early,
        mock_calc_tardiness,
        mock_calc_actual_working_hours,
    ):
        # 正常に勤怠記録の各フィールドが計算されて設定されること
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result.stepping_out, Const.TD_ZERO)
        self.assertEqual(result.actual_work, timedelta(hours=8))
        self.assertEqual(result.late, timedelta(minutes=0))
        self.assertEqual(result.early_leave, timedelta(minutes=0))
        self.assertEqual(result.over, timedelta(hours=1))
        self.assertEqual(result.over_8h, timedelta(hours=1))
        self.assertEqual(result.night, timedelta(minutes=0))

    @patch("sao.core.calc_actual_working_hours", return_value=timedelta(hours=8))
    @patch("sao.core.calendar_is_holiday", return_value=True)
    @patch("sao.core.is_legal_holiday", return_value=True)
    @patch("sao.core.calc_tardiness", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_leave_early", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_overtime", return_value=timedelta(hours=1))
    @patch("sao.core.calc_over_8h", return_value=timedelta(hours=1))
    @patch("sao.core.calc_midnight_work", return_value=timedelta(minutes=0))
    @patch("sao.core.has_permitted_overtime_work", return_value=True)
    def test_update_attendance_record_and_save_sets_holiday_fields(
        self,
        mock_has_permitted_overtime_work,
        mock_calc_midnight_work,
        mock_calc_over_8h,
        mock_calc_overtime,
        mock_calc_leave_early,
        mock_calc_tardiness,
        mock_is_legal_holiday,
        mock_calendar_is_holiday,
        mock_calc_actual_working_hours,
    ):
        # 法定休日の場合、legal_holidayフィールドが設定されること
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result.legal_holiday, timedelta(hours=8))

    @patch("sao.core.calc_actual_working_hours", return_value=timedelta(hours=8))
    @patch("sao.core.calendar_is_holiday", return_value=True)
    @patch("sao.core.is_legal_holiday", return_value=False)
    @patch("sao.core.calc_tardiness", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_leave_early", return_value=timedelta(minutes=0))
    @patch("sao.core.calc_overtime", return_value=timedelta(hours=1))
    @patch("sao.core.calc_over_8h", return_value=timedelta(hours=1))
    @patch("sao.core.calc_midnight_work", return_value=timedelta(minutes=0))
    @patch("sao.core.has_permitted_overtime_work", return_value=True)
    def test_update_attendance_record_and_save_sets_non_legal_holiday_fields(
        self,
        mock_has_permitted_overtime_work,
        mock_calc_midnight_work,
        mock_calc_over_8h,
        mock_calc_overtime,
        mock_calc_leave_early,
        mock_calc_tardiness,
        mock_is_legal_holiday,
        mock_calendar_is_holiday,
        mock_calc_actual_working_hours,
    ):
        # 休日だが法定休日でない場合、legal_holidayフィールドは設定されないこと
        result = update_attendance_record_and_save(self.attendance)
        self.assertEqual(result.holiday, timedelta(hours=8))
        self.assertEqual(result.legal_holiday, timedelta(0))


class TestFinalizeDailyRecord(TestCase):
    def setUp(self):
        self.employee = create_employee(create_user())
        self.day = date(2023, 8, 2)

    @patch("sao.core.EmployeeDailyRecord.objects")
    def test_skip_if_record_exists(self, mock_objects):
        # 既に勤務記録が存在する場合、処理をスキップすること
        mock_objects.filter.return_value.exists.return_value = True
        with patch("sao.core.logger") as mock_logger:
            result = finalize_daily_record(self.employee, self.day)
            mock_logger.info.assert_called_with(
                "[test]勤務記録が既に存在しているためスキップします"
            )
            self.assertIsNone(result)

    @patch("sao.core.EmployeeDailyRecord.objects")
    @patch(
        "sao.core.get_daily_webstamps",
        return_value=[datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)],
    )
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_stepout_periods", return_value=[])
    @patch("sao.core.generate_daily_record")
    @patch("sao.core.generate_attendance_record")
    @patch("sao.core.initiate_daily_attendance_record")
    @patch("sao.core.update_attendance_record_and_save")
    @patch("sao.core.generate_stepout_records")
    @patch("sao.core.remove_daily_webstamps")
    def test_finalize_creates_records(
        self,
        mock_remove_daily_webstamps,
        mock_generate_stepout_records,
        mock_update_attendance_record_and_save,
        mock_initiate_daily_attendance_record,
        mock_generate_attendance_record,
        mock_generate_daily_record,
        mock_get_stepout_periods,
        mock_get_employee_hour,
        mock_get_daily_webstamps,
        mock_objects,
    ):
        # Setup mocks for record creation
        mock_objects.filter.return_value.exists.side_effect = [False, True]
        mock_record = MagicMock()
        mock_generate_daily_record.return_value = mock_record
        mock_attendance = MagicMock()
        mock_generate_attendance_record.return_value = mock_attendance
        mock_initiate_daily_attendance_record.return_value = mock_attendance
        mock_update_attendance_record_and_save.return_value = mock_attendance
        mock_get_employee_hour.return_value.get_period.return_value = MagicMock()
        with patch(
            "sao.core.DailyAttendanceRecord.objects"
        ) as mock_attn_objects, patch("sao.core.logger") as mock_logger, patch(
            "sao.core.transaction.atomic"
        ):
            mock_attn_objects.filter.return_value.exists.return_value = True
            result = finalize_daily_record(self.employee, self.day)
            mock_generate_daily_record.assert_called()
            mock_generate_attendance_record.assert_called()
            mock_initiate_daily_attendance_record.assert_called()
            mock_update_attendance_record_and_save.assert_called()
            mock_generate_stepout_records.assert_called()
            mock_remove_daily_webstamps.assert_called()
            mock_logger.info.assert_any_call("[test]EmployeeDailyRecordを生成しました")
            mock_logger.info.assert_any_call(
                "[test]DailyAttendanceRecordを生成しました"
            )
            self.assertIsNone(result)

    @patch("sao.core.EmployeeDailyRecord.objects")
    @patch("sao.core.get_daily_webstamps", return_value=[])
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_stepout_periods", return_value=[])
    @patch("sao.core.generate_daily_record", return_value=None)
    def test_finalize_skips_if_no_record(
        self,
        mock_generate_daily_record,
        mock_get_stepout_periods,
        mock_get_employee_hour,
        mock_get_daily_webstamps,
        mock_objects,
    ):
        mock_objects.filter.return_value.exists.return_value = False
        with patch("sao.core.logger") as mock_logger, patch(
            "sao.core.transaction.atomic"
        ):
            result = finalize_daily_record(self.employee, self.day)
            mock_logger.info.assert_called_with(
                "[test]打刻データが存在しないためスキップします"
            )
            self.assertIsNone(result)

    @patch("sao.core.EmployeeDailyRecord.objects")
    @patch("sao.core.get_daily_webstamps", return_value=[])
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_stepout_periods", return_value=[])
    @patch("sao.core.generate_daily_record", side_effect=Exception("error"))
    def test_finalize_handles_exception(
        self,
        mock_generate_daily_record,
        mock_get_stepout_periods,
        mock_get_employee_hour,
        mock_get_daily_webstamps,
        mock_objects,
    ):
        mock_objects.filter.return_value.exists.return_value = False
        with patch("sao.core.logger") as mock_logger, patch(
            "sao.core.transaction.atomic"
        ):
            result = finalize_daily_record(self.employee, self.day)
            mock_logger.error.assert_called()
            self.assertIsNone(result)

    @patch("sao.core.EmployeeDailyRecord.objects")
    @patch("sao.core.get_daily_webstamps", return_value=[datetime(2023, 8, 2, 10, 0)])
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_stepout_periods", return_value=[])
    @patch("sao.core.generate_daily_record")
    @patch("sao.core.generate_attendance_record")
    @patch("sao.core.initiate_daily_attendance_record")
    @patch("sao.core.update_attendance_record_and_save")
    @patch("sao.core.generate_stepout_records")
    @patch("sao.core.remove_daily_webstamps")
    def test_finalize_missing_employee_daily_record(
        self,
        mock_remove_daily_webstamps,
        mock_generate_stepout_records,
        mock_update_attendance_record_and_save,
        mock_initiate_daily_attendance_record,
        mock_generate_attendance_record,
        mock_generate_daily_record,
        mock_get_stepout_periods,
        mock_get_employee_hour,
        mock_get_daily_webstamps,
        mock_objects,
    ):
        # EmployeeDailyRecord not created
        mock_objects.filter.return_value.exists.side_effect = [False, False]
        mock_record = MagicMock()
        mock_generate_daily_record.return_value = mock_record
        mock_attendance = MagicMock()
        mock_generate_attendance_record.return_value = mock_attendance
        mock_initiate_daily_attendance_record.return_value = mock_attendance
        mock_update_attendance_record_and_save.return_value = mock_attendance
        mock_get_employee_hour.return_value.get_period.return_value = MagicMock()
        with patch(
            "sao.core.DailyAttendanceRecord.objects"
        ) as mock_attn_objects, patch("sao.core.logger") as mock_logger, patch(
            "sao.core.transaction.atomic"
        ):
            mock_attn_objects.filter.return_value.exists.return_value = True
            result = finalize_daily_record(self.employee, self.day)
            mock_logger.error.assert_any_call(
                f"[test]EmployeeDailyRecordが生成されませんでした: {self.employee} {self.day}"
            )
            self.assertIsNone(result)

    @patch("sao.core.EmployeeDailyRecord.objects")
    @patch("sao.core.get_daily_webstamps", return_value=[datetime(2023, 8, 2, 10, 0)])
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_stepout_periods", return_value=[])
    @patch("sao.core.generate_daily_record")
    @patch("sao.core.generate_attendance_record")
    @patch("sao.core.initiate_daily_attendance_record")
    @patch("sao.core.update_attendance_record_and_save")
    @patch("sao.core.generate_stepout_records")
    @patch("sao.core.remove_daily_webstamps")
    def test_finalize_missing_daily_attendance_record(
        self,
        mock_remove_daily_webstamps,
        mock_generate_stepout_records,
        mock_update_attendance_record_and_save,
        mock_initiate_daily_attendance_record,
        mock_generate_attendance_record,
        mock_generate_daily_record,
        mock_get_stepout_periods,
        mock_get_employee_hour,
        mock_get_daily_webstamps,
        mock_objects,
    ):
        # DailyAttendanceRecord not created
        mock_objects.filter.return_value.exists.side_effect = [False, True]
        mock_record = MagicMock()
        mock_generate_daily_record.return_value = mock_record
        mock_attendance = MagicMock()
        mock_generate_attendance_record.return_value = mock_attendance
        mock_initiate_daily_attendance_record.return_value = mock_attendance
        mock_update_attendance_record_and_save.return_value = mock_attendance
        mock_get_employee_hour.return_value.get_period.return_value = MagicMock()
        with patch(
            "sao.core.DailyAttendanceRecord.objects"
        ) as mock_attn_objects, patch("sao.core.logger") as mock_logger, patch(
            "sao.core.transaction.atomic"
        ):
            mock_attn_objects.filter.return_value.exists.return_value = False
            result = finalize_daily_record(self.employee, self.day)
            mock_logger.error.assert_any_call(
                f"DailyAttendanceRecordが生成されませんでした: {self.employee} {self.day}"
            )
            self.assertIsNone(result)
