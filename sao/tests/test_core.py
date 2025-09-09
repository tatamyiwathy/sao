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
    WebTimeStamp
)
from sao.tests.utils import (
    create_working_hours,
    set_office_hours_to_employee,
    create_time_stamp_data,
    TOTAL_ACTUAL_WORKING_TIME,
)
from sao.utils import (
    tally_over_work_time,
    tally_attendances
)
from sao.core import (
    adjust_working_hours,
    calc_assumed_working_time,
    round_down,
    round_stamp,
    round_result,
    get_adjusted_start_time,
    get_adjust_end_time,
    calc_tardiness,
    calc_leave_early,
    tally_steppingout,
    calc_overtime,
    calc_over_8h,
    calc_midnight_work,
    calc_legal_holiday,
    calc_holiday,
    accumulate_weekly_working_hours,
    is_permit_overtime,
    get_half_year_day,
    get_annual_paied_holiday_days,
    get_recent_day_of_annual_leave_update,
    is_need_break_time,
    collect_timerecord_by_month,
    get_employee_hour,
    get_working_hours_by_category,
    get_working_hours_tobe_assign,
    calc_actual_working_time,
    get_day_switch_time,
    normalize_to_business_day,
    get_clock_in_out,
    generate_daily_record,
    get_attendance_in_period,
    finalize_daily_record
)
from sao.const import Const
from sao.calendar import monthdays, is_holiday
from sao.working_status import WorkingStatus
from django.test import TestCase
from unittest.mock import patch, MagicMock
from sao.period import Period


# class TallyMonthAttendancesTest(TestCase):
#     """月の勤怠を集計するテスト"""

#     def setUp(self):
#         self.day = date(2021, 8, 6)
#         self.emp = create_employee(create_user(), include_overtime_pay=True)
#         self.today = date(year=2020, month=1, day=23)
#         create_working_hours()
#         create_time_stamp_data(self.emp)  # 月の勤怠データを生成

#     def test_tally_monthly_attendance(self):
#         set_office_hours_to_employee(
#             self.emp, date(1900, 1, 1), get_working_hours_by_category("A")
#         )

#         # 勤怠記録収集
#         records = collect_timerecord_by_month(self.emp, self.day)
#         self.assertEqual(len(records), monthdays(self.day))

#         # 勤怠記録を集計
#         results = attendance.tally_monthly_attendance(self.day.month, records)
#         self.assertEqual(len(results), monthdays(self.day))

#         # self.assertEqual(results[5].date, date(2021, 9, 6))

#         for r in results:
#             self.assertTrue(r.is_valid())

#     def test_tally_month_attendances_empty(self):
#         set_office_hours_to_employee(
#             self.emp, date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         # 勤怠記録がない場合
#         records = collect_timerecord_by_month(self.emp, self.day)
#         self.assertEqual(len(records), monthdays(self.day))

#         results = attendance.tally_monthly_attendance(self.day.month, records)
#         self.assertEqual(len(results), monthdays(self.day))


class AccumulateWeeklyWorkingHoursTest(TestCase):

    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()

    def test_accumulate_weekly_working_hours(self) -> None:
        create_time_stamp_data(self.employee)
        set_office_hours_to_employee(
            self.employee, date(1900, 1, 1), get_working_hours_by_category("A")
        )
        records = collect_timerecord_by_month(self.employee, date(2021, 8, 1))
        results = accumulate_weekly_working_hours(records)
        week = 1
        for r in results:
            self.assertEqual(r[0], week)
            week += 1

    def test_accumulate_weekly_working_hours_when_empty(self) -> None:
        EmployeeDailyRecord.objects.all().delete()
        """勤怠記録がない場合の週間勤務時間集計のテスト"""
        set_office_hours_to_employee(
            self.employee, date(1900, 1, 1), get_working_hours_by_category("A")
        )
        records = collect_timerecord_by_month(self.employee, date(2021, 8, 1))
        results = accumulate_weekly_working_hours(records)
        week = 1
        for r in results:
            self.assertEqual(r[0], week)
            week += 1


# class TestSumupAttendances(TestCase):
#     def test_sumup_attendances(self):
#         employee = create_employee(create_user(), include_overtime_pay=True)
#         create_time_stamp_data(employee)
#         create_working_hours()
#         set_office_hours_to_employee(
#             employee, date(1901, 1, 1), get_working_hours_by_category("A")
#         )
#         period = Period(datetime(2021, 8, 1,0,0), datetime(2021, 9, 1,0,0))
#         attendances = get_attendance_in_period(employee, period.start.date(), period.end.date())
#         print(len(attendances))
#         attendances[-1].total_over = tally_over_work_time(8, attendances)
#         summed_up = tally_attendances(attendances)
#         self.assertEqual(summed_up["work"], TOTAL_ACTUAL_WORKING_TIME)
#         self.assertEqual(summed_up["late"], Const.TD_3H)  # 遅刻
#         self.assertEqual(summed_up["before"], timedelta(minutes=24))  # 早退
#         self.assertEqual(summed_up["steppingout"], timedelta(minutes=0))
#         self.assertEqual(summed_up["out_of_time"], timedelta(seconds=61560))
#         self.assertEqual(summed_up["over_8h"], timedelta(seconds=61560))
#         self.assertEqual(summed_up["night"], timedelta(seconds=3060))
#         self.assertEqual(summed_up["legal_holiday"], timedelta(hours=0))
#         self.assertEqual(summed_up["holiday"], timedelta(seconds=11580))
#         self.assertEqual(summed_up["accumulated_overtime"], timedelta(seconds=61560))


class TestRoundDown(TestCase):
    def test_round_down(self):
        t = timedelta(seconds=1700)
        self.assertEqual(round_down(t), timedelta(seconds=0))
        t = timedelta(seconds=1900)
        self.assertEqual(round_down(t), timedelta(minutes=30))


class TestRoundStamp(TestCase):
    def test_round_stamp(self):
        t = timedelta(seconds=13 * 3600 + 28 * 60)
        value = round_stamp(t)
        self.assertEqual(value, timedelta(seconds=13 * 3600))

        t = timedelta(seconds=13 * 3600 + 35 * 60)
        value = round_stamp(t)
        self.assertEqual(value, timedelta(seconds=14 * 3600))


# class TestRoundResult(TestCase):
#     def test_round_result(self):
#         employee = create_employee(create_user(), include_overtime_pay=True)
#         create_time_stamp_data(employee)
#         create_working_hours()
#         set_office_hours_to_employee(
#             employee, date(1901, 1, 1), get_working_hours_by_category("A")
#         )
#         attendances = attendance.tally_monthly_attendance(8, EmployeeDailyRecord.objects.all())
#         summed_up = attendance.sumup_attendances(attendances)
#         rounded_result = round_result(summed_up)
#         self.assertEqual(
#             rounded_result["work"], timedelta(seconds=6 * 24 * 3600 + 90 * 60)
#         )


class TestGetAdjustedStartingTime(TestCase):
    def test_get_adjusted_starting_time(self):

        day = date(2021, 8, 2)
        time_record = EmployeeDailyRecord(
            date=day,
            clock_in=datetime.combine(day, time(9, 30)),
        )
        starting_time = get_adjusted_start_time(
            time_record, datetime.combine(time_record.date, time(10, 0))
        )
        self.assertEqual(starting_time, datetime.combine(time_record.date, time(10, 0)))


class TestGetAdjustedClosingTime(TestCase):
    def test_get_adjusted_closing_time(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user(), include_overtime_pay=True)
        time_record = EmployeeDailyRecord(
            date=d,
            employee=employee,
            clock_in=datetime.combine(d, time(9, 0)),
            clock_out=datetime.combine(d, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )
        closing_time = get_adjust_end_time(
            time_record, datetime.combine(d, time(19, 0)), True
        )
        self.assertEqual(closing_time, datetime.combine(d, time(19, 0)))


class TestCalcActualWorkingHours(TestCase):
    def test_calc_actual_working_hours(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user(), include_overtime_pay=True)
        time_record = EmployeeDailyRecord(
            date=d,
            employee=employee,
            clock_in=datetime.combine(d, time(9, 0)),
            clock_out=datetime.combine(d, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )

        starting_time = datetime.combine(d, time(10, 0))
        closing_time = datetime.combine(d, time(19, 0))
        actual_working_hours = calc_actual_working_time(
            time_record, starting_time, closing_time, timedelta(0)
        )
        self.assertEqual(actual_working_hours, timedelta(hours=8))


class TestCalcTardiness(TestCase):
    def test_calc_tardy(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user(), include_overtime_pay=True)
        time_record = EmployeeDailyRecord(
            date=d,
            employee=employee,
            clock_in=datetime.combine(d, time(10, 15)),
            clock_out=datetime.combine(d, time(19, 0)),
            status=WorkingStatus.C_KINMU,
        )

        starting_time = datetime.combine(time_record.date, time(10, 0))
        tardy = calc_tardiness(time_record, starting_time)
        self.assertEqual(tardy, timedelta(minutes=15))


class TestCalcLeaveEarly(TestCase):
    def test_calc_sotai(self):
        d = date(2021, 8, 2)
        employee = create_employee(create_user(), include_overtime_pay=True)
        time_record = EmployeeDailyRecord(
            date=d,
            employee=employee,
            clock_in=datetime.combine(d, time(10, 00)),
            clock_out=datetime.combine(d, time(18, 0)),
            status=WorkingStatus.C_KINMU,
        )

        closing_time = datetime.combine(d, time(19, 0))
        leave_early_time = calc_leave_early(time_record, closing_time)
        self.assertEqual(leave_early_time, timedelta(minutes=60))


class TestTallySteppingOut(TestCase):
    """外出時間を集計するテスト"""

    def test_tally_steppingout(self):
        employee = create_employee(create_user(), include_overtime_pay=True)
        SteppingOut(
            employee=employee,
            out_time=datetime(2021, 8, 2, 13, 0, 0),
            return_time=datetime(2021, 8, 2, 14, 0, 0),
        ).save()
        create_time_stamp_data(employee)
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 2))
        total_stepping_out = tally_steppingout(time_record)
        self.assertEqual(total_stepping_out, Const.TD_1H)

    def test_tally_steppingout_when_empty(self):
        employee = create_employee(create_user(), include_overtime_pay=True)
        create_time_stamp_data(employee)
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 2))
        total_stepping_out = tally_steppingout(time_record)
        self.assertEqual(total_stepping_out, Const.TD_ZERO)


class TestCalcOvertime(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.employee, date(1901, 1, 1), get_working_hours_by_category("A")
        )
        create_time_stamp_data(self.employee)

    def test_calc_overtime(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 3))
        working_hours = adjust_working_hours(time_record)
        period = calc_assumed_working_time(
            time_record, working_hours.start, working_hours.end
        )
        working_time = calc_actual_working_time(
            time_record, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        overtime = calc_overtime(time_record, working_time, period)
        self.assertEqual(overtime, timedelta(hours=1))

    def test_calc_overtime_on_holiday(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 1))  # 日曜日
        working_hours = adjust_working_hours(time_record)
        period = calc_assumed_working_time(
            time_record, working_hours.start, working_hours.end
        )
        working_time = calc_actual_working_time(
            time_record, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        overtime = calc_overtime(time_record, working_time, period)
        self.assertEqual(overtime, timedelta(hours=0))

    def test_when_absent(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 23))
        working_hours = adjust_working_hours(time_record)
        period = calc_assumed_working_time(
            time_record, working_hours.start, working_hours.end
        )
        working_time = calc_actual_working_time(
            time_record, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        overtime = calc_overtime(time_record, working_time, period)
        self.assertEqual(overtime, timedelta(hours=0))


class TestCalcOver8h(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.employee, date(1901, 1, 1), get_working_hours_by_category("A")
        )
        create_time_stamp_data(self.employee)

    def test_calc_over_8h(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 3))
        working_hours = adjust_working_hours(time_record)
        working_time = calc_actual_working_time(
            time_record, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        over_8h = calc_over_8h(time_record, working_time)
        self.assertEqual(over_8h, timedelta(hours=1))


class TestCalcMidnightWork(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.employee, date(1901, 1, 1), get_working_hours_by_category("A")
        )
        create_time_stamp_data(self.employee)

    def test_calc_midnight_work(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 31))
        midnight_work = calc_midnight_work(time_record)
        self.assertEqual(midnight_work, timedelta(minutes=51))


class TestCalcLegalHoliday(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.employee, date(1901, 1, 1), get_working_hours_by_category("A")
        )
        create_time_stamp_data(self.employee)

    def test_calc_legal_holiday(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 1))
        legal_holiday = calc_legal_holiday(time_record, timedelta(hours=8))
        self.assertEqual(legal_holiday, timedelta(hours=8))

    def test_calc_workiday(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 2))
        legal_holiday = calc_legal_holiday(time_record, timedelta(hours=8))
        self.assertEqual(legal_holiday, timedelta(hours=0))


class TestCalcHoliday(TestCase):
    def setUp(self) -> None:
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.employee, date(1901, 1, 1), get_working_hours_by_category("A")
        )
        create_time_stamp_data(self.employee)

    def test_calc_holiday(self):
        time_record = EmployeeDailyRecord.objects.get(date=date(2021, 8, 9))
        self.assertTrue(is_holiday(time_record.date))
        actual_working_hours = timedelta(hours=8)
        holiday = calc_holiday(time_record, actual_working_hours)
        self.assertEqual(holiday, timedelta(hours=8))


# class TestCountDays(TestCase):
#     def test_count_days(self):
#         start_date = date(2021, 1, 1)
#         end_date = date(2021, 1, 31)
#         days = count_days(start_date, end_date)
#         self.assertEqual(days, 31)


class TestIsPermitOvertime(TestCase):
    def test_is_permit_overtime(self):
        employee = create_employee(create_user(), include_overtime_pay=True)
        permit_overtime = is_permit_overtime(employee)
        self.assertTrue(permit_overtime)

    def test_not_permit_overtime(self):
        employee = create_employee(create_user(), include_overtime_pay=False)
        permit_overtime = is_permit_overtime(employee)
        self.assertFalse(permit_overtime)


class TestGetHalfYearDay(TestCase):
    def test_get_half_year_day(self):
        half_year_day = get_half_year_day(datetime(2021, 1, 1, 0, 0, 0))
        self.assertEqual(half_year_day, datetime(2021, 7, 1, 0, 0, 0))

    def test_get_half_year_day_when_leap_year(self):
        half_year_day = get_half_year_day(datetime(2020, 2, 29, 0, 0, 0))
        self.assertEqual(half_year_day, datetime(2020, 8, 29, 0, 0, 0))


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
    def test_get_recent_day_of_annual_leave_update(self):
        join_date = date(2021, 1, 1)
        recent_day_of_annual_leave_update = get_recent_day_of_annual_leave_update(
            2021, join_date
        )
        after_half_year = get_half_year_day(join_date)
        self.assertEqual(recent_day_of_annual_leave_update, after_half_year)

    def test_alter_year(self):
        join_date = date(2021, 1, 1)
        recent_day_of_annual_leave_update = get_recent_day_of_annual_leave_update(
            2022, join_date
        )
        self.assertEqual(recent_day_of_annual_leave_update, date(2022, 7, 1))

    def test_get_recent_day_of_annual_leave_update_when_leap_year(self):
        join_date = date(2020, 2, 29)
        recent_day_of_annual_leave_update = get_recent_day_of_annual_leave_update(
            2020, join_date
        )
        after_half_year = get_half_year_day(join_date)
        self.assertEqual(recent_day_of_annual_leave_update, after_half_year)


class TestIsNeedBreakTime(TestCase):
    def test_need_break_time(self):
        # 6時間超労働で休息が必要
        work_period = timedelta(hours=8)
        status = WorkingStatus.C_KINMU
        need_break_time = is_need_break_time(work_period, status)
        self.assertTrue(need_break_time)

    def test_no_need_break_time(self):
        # 6時間超労働で休息が必要
        work_period = timedelta(hours=6)
        status = WorkingStatus.C_KINMU
        need_break_time = is_need_break_time(work_period, status)
        self.assertFalse(need_break_time)

    def test_when_alternoon_off_with_rest(self):
        # 午後休で休息が必要
        work_period = timedelta(hours=5)
        status = WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI
        need_break_time = is_need_break_time(work_period, status)
        self.assertTrue(need_break_time)


class TestCollectTimeRecordByMonth(TestCase):
    def test_collect_timerecord_by_month(self):
        emp = create_employee(create_user(), include_overtime_pay=True)
        create_time_stamp_data(emp)  # 打刻データ生成
        create_working_hours()
        set_office_hours_to_employee(
            emp, date(1901, 1, 1), get_working_hours_by_category("A")
        )

        records = collect_timerecord_by_month(emp, date(2021, 8, 1))
        self.assertEqual(len(records), monthdays(date(2021, 8, 1)))


class TestGetOfficeHours(TestCase):
    def test_get_office_hours(self):
        emp = create_employee(create_user(), include_overtime_pay=True)
        create_time_stamp_data(emp)
        create_working_hours()
        set_office_hours_to_employee(
            emp, date(1901, 1, 1), get_working_hours_by_category("A")
        )

        office_hours = get_employee_hour(emp, date(2021, 8, 1))
        self.assertEqual(office_hours.begin_time, Const.OCLOCK_1000)
        self.assertEqual(office_hours.end_time, Const.OCLOCK_1900)


class TestGetWorkingHoursByCategory(TestCase):
    def test_get_working_hours_by_category(self):
        create_working_hours()
        working_hours = get_working_hours_by_category("A")
        self.assertEqual(working_hours.begin_time, Const.OCLOCK_1000)
        self.assertEqual(working_hours.end_time, Const.OCLOCK_1900)


class TestGetWorkingHoursToBeAssign(TestCase):
    def test_get_working_hours_tobe_assign(self):
        emp = create_employee(create_user(), include_overtime_pay=True)
        create_time_stamp_data(emp)
        create_working_hours()
        set_office_hours_to_employee(
            emp, date(1901, 1, 1), get_working_hours_by_category("A")
        )

        working_hours = get_working_hours_tobe_assign(emp).working_hours
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
        normalized = normalize_to_business_day(dt)
        self.assertEqual(normalized, datetime(2021, 8, 1, 4, 30))

    def test_normalize_to_business_day_at_switch_time(self):
        # 5:00 AM, should not normalize
        dt = datetime(2021, 8, 2, 5, 0)
        normalized = normalize_to_business_day(dt)
        self.assertEqual(normalized, dt)

    def test_normalize_to_business_day_after_switch_time(self):
        # 6:00 AM, should not normalize
        dt = datetime(2021, 8, 2, 6, 0)
        normalized = normalize_to_business_day(dt)
        self.assertEqual(normalized, dt)


class TestAdjustWorkingHours(TestCase):
    def setUp(self):
        # Minimal Employee mock
        self.employee = Employee(name="Test Employee")
        # Standard working hours: 10:00-19:00
        self.working_hour = WorkingHour(begin_time=Const.OCLOCK_1000, end_time=Const.OCLOCK_1900)
        self.day = date(2023, 8, 2)

    @patch("sao.core.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    def test_normal_workday(self, mock_get_employee_hour, mock_is_holiday):
        # 平日、出勤退勤あり
        mock_get_employee_hour.return_value = self.working_hour
        wh_start = datetime.combine(self.day, self.working_hour.begin_time)
        wh_end = datetime.combine(self.day, self.working_hour.end_time)
        record = EmployeeDailyRecord(date=self.day, employee=self.employee, 
                                        working_hours_start=wh_start,
                                        working_hours_end=wh_end,
                                     status=WorkingStatus.C_KINMU)
        working_hours = adjust_working_hours(record)
        self.assertEqual(working_hours.start, datetime.combine(self.day, Const.OCLOCK_1000))
        self.assertEqual(working_hours.end, datetime.combine(self.day, Const.OCLOCK_1900))

    @patch("sao.core.is_holiday", return_value=True)
    def test_holiday_work(self, mock_is_holiday):
        # 休日出勤、出勤退勤あり->打刻そのまま
        record = EmployeeDailyRecord(
            date=self.day,
            employee=self.employee,
            clock_in=datetime.combine(self.day, time(9, 0)),
            clock_out=datetime.combine(self.day, time(18, 0)),
            status=WorkingStatus.C_KINMU,
        )
        working_hours = adjust_working_hours(record)
        self.assertEqual(working_hours.start, datetime.combine(self.day, time(9, 0)))
        self.assertEqual(working_hours.end, datetime.combine(self.day, time(18, 0)))

    @patch("sao.core.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    def test_morning_off(self, mock_get_employee_hour, mock_is_holiday):
        # 午前休
        mock_get_employee_hour.return_value = self.working_hour
        wh_start = datetime.combine(self.day, self.working_hour.begin_time)
        wh_end = datetime.combine(self.day, self.working_hour.end_time)
        record = EmployeeDailyRecord(date=self.day, employee=self.employee, 
                                     working_hours_start=wh_start,
                                     working_hours_end=wh_end,
                                     status=WorkingStatus.C_YUUKYUU_GOZENKYU)
        working_hours = adjust_working_hours(record)
        # Duration = 9h, minus 1h rest = 8h, half = 4h
        expected_start = datetime.combine(self.day, Const.OCLOCK_1000) + timedelta(hours=4) + Const.TD_1H
        expected_end = datetime.combine(self.day, Const.OCLOCK_1900)
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    @patch("sao.core.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    def test_afternoon_off_with_rest(self, mock_get_employee_hour, mock_is_holiday):
        # 午後休（休息あり）
        mock_get_employee_hour.return_value = self.working_hour
        wh_start = datetime.combine(self.day, self.working_hour.begin_time)
        wh_end = datetime.combine(self.day, self.working_hour.end_time)
        record = EmployeeDailyRecord(date=self.day, employee=self.employee, 
                                        working_hours_start=wh_start,
                                        working_hours_end=wh_end,
                                     status=WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI)
        working_hours = adjust_working_hours(record)
        # Duration = 9h, minus 1h rest = 8h, half = 4h
        expected_start = datetime.combine(self.day, Const.OCLOCK_1000)
        expected_end = datetime.combine(self.day, Const.OCLOCK_1900) - timedelta(hours=4)
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    @patch("sao.core.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    def test_afternoon_off_no_rest(self, mock_get_employee_hour, mock_is_holiday):
        # 午後休（休息なし）
        mock_get_employee_hour.return_value = self.working_hour
        wh_start = datetime.combine(self.day, self.working_hour.begin_time)
        wh_end = datetime.combine(self.day, self.working_hour.end_time)
        record = EmployeeDailyRecord(date=self.day, employee=self.employee, 
                                        working_hours_start=wh_start,
                                        working_hours_end=wh_end,
                                     status=WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI)
        working_hours = adjust_working_hours(record)
        # Duration = 9h, minus 1h rest = 8h, half = 4h, minus 1h rest
        expected_start = datetime.combine(self.day, Const.OCLOCK_1000)
        expected_end = datetime.combine(self.day, Const.OCLOCK_1900) - timedelta(hours=4) - Const.TD_1H
        self.assertEqual(working_hours.start, expected_start)
        self.assertEqual(working_hours.end, expected_end)

    @patch("sao.core.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    def test_short_working_hours_no_rest(self, mock_get_employee_hour, mock_is_holiday):
        # 勤務時間が６時間以下、休息なし
        # Working hour less than 6h, no rest adjustment
        short_working_hour = WorkingHour(begin_time=time(10, 0), end_time=time(15, 0))
        mock_get_employee_hour.return_value = short_working_hour

        working_hours_start = datetime.combine(self.day, short_working_hour.begin_time)
        working_hours_end = datetime.combine(self.day, short_working_hour.end_time)
        record = EmployeeDailyRecord(date=self.day, employee=self.employee, 
                                     working_hours_start=working_hours_start,
                                     working_hours_end=working_hours_end,
                                     status=WorkingStatus.C_KINMU)
        working_hours = adjust_working_hours(record)
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
    def setUp(self):
        self.employee = create_employee(create_user(), include_overtime_pay=True)
        self.day = date(2023, 8, 2)
        self.working_hour = WorkingHour(begin_time=time(10, 0), end_time=time(19, 0))
        self.period = Period(
            datetime.combine(self.day, time(10, 0)),
            datetime.combine(self.day, time(19, 0)),
        )

    @patch("sao.working_status.get_working_status", return_value=WorkingStatus.C_KINMU)
    @patch("sao.calendar.is_legal_holiday", return_value=False)
    @patch("sao.calendar.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_clock_in_out")
    def test_generate_daily_record_normal(
        self, mock_get_clock_in_out, mock_get_employee_hour, mock_is_holiday, mock_is_legal_holiday, mock_get_working_status
    ):
        # 平日、出勤退勤あり
        # Setup
        stamps = [datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)]
        mock_get_clock_in_out.return_value = Period(stamps[0], stamps[1])
        mock_get_employee_hour.return_value = self.working_hour
        self.working_hour.get_paired_time = MagicMock(return_value=self.period)

        # Act
        generate_daily_record(stamps, self.employee, self.day)

        # Assert
        record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.clock_in, stamps[0])
        self.assertEqual(record.clock_out, stamps[1])
        self.assertEqual(record.working_hours_start, self.period.start)
        self.assertEqual(record.working_hours_end, self.period.end)
        self.assertEqual(record.status, WorkingStatus.C_KINMU)


    @patch("sao.working_status.get_working_status", return_value=WorkingStatus.C_KEKKIN)
    @patch("sao.calendar.is_legal_holiday", return_value=False)
    @patch("sao.calendar.is_holiday", return_value=False)
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_clock_in_out")
    def test_generate_daily_record_no_stamp(
        self, mock_get_clock_in_out, mock_get_employee_hour, mock_is_holiday, mock_is_legal_holiday, mock_get_working_status
    ):
        # 平日、出勤退勤なし
        stamps = []
        mock_get_clock_in_out.return_value = Period(None, None)
        mock_get_employee_hour.return_value = self.working_hour
        self.working_hour.get_paired_time = MagicMock(return_value=self.period)

        # Act
        generate_daily_record(stamps, self.employee, self.day)

        # Assert
        record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.clock_in, None)
        self.assertEqual(record.clock_out, None)
        self.assertEqual(record.working_hours_start, self.period.start)
        self.assertEqual(record.working_hours_end, self.period.end)
        self.assertEqual(record.status, WorkingStatus.C_KEKKIN)

    @patch("sao.core.get_working_status", return_value=WorkingStatus.C_HOUTEIGAI_KYUJITU)
    @patch("sao.core.is_legal_holiday", return_value=False)
    @patch("sao.core.is_holiday", return_value=True)
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_clock_in_out")
    def test_generate_daily_record_holiday(
        self, mock_get_clock_in_out, mock_get_employee_hour, mock_is_holiday, mock_is_legal_holiday, mock_get_working_status
    ):
        # 法定外休日、出勤退勤あり->打刻そのまま
        # Setup
        stamps = [datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)]
        mock_get_clock_in_out.return_value = Period(stamps[0], stamps[1])
        mock_get_employee_hour.return_value = self.working_hour
        # get_paired_time should not be called, but if it is, return normal
        self.working_hour.get_paired_time = MagicMock(return_value=self.period)

        # Act
        generate_daily_record(stamps, self.employee, self.day)

        # Assert
        record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.working_hours_start, None)
        self.assertEqual(record.working_hours_end, None)
        self.assertEqual(record.clock_in, stamps[0])
        self.assertEqual(record.clock_out, stamps[1])
        self.assertEqual(record.status, WorkingStatus.C_HOUTEIGAI_KYUJITU)


    @patch("sao.core.get_working_status", return_value=WorkingStatus.C_HOUTEI_KYUJITU)
    @patch("sao.core.is_legal_holiday", return_value=True)
    @patch("sao.core.is_holiday", return_value=True)
    @patch("sao.core.get_employee_hour")
    @patch("sao.core.get_clock_in_out")
    def test_generate_daily_record_legal_holiday(
        self, mock_get_clock_in_out, mock_get_employee_hour, mock_is_holiday, mock_is_legal_holiday, mock_get_working_status
    ):
        # 法定休日、出勤退勤あり->打刻そのまま
        # Setup
        stamps = [datetime(2023, 8, 2, 10, 0), datetime(2023, 8, 2, 19, 0)]
        mock_get_clock_in_out.return_value = Period(stamps[0], stamps[1])
        mock_get_employee_hour.return_value = self.working_hour
        # get_paired_time should not be called, but if it is, return normal
        self.working_hour.get_paired_time = MagicMock(return_value=self.period)

        # Act
        generate_daily_record(stamps, self.employee, self.day)

        # Assert
        record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.working_hours_start, None)
        self.assertEqual(record.working_hours_end, None)
        self.assertEqual(record.clock_in, stamps[0])
        self.assertEqual(record.clock_out, stamps[1])
        self.assertEqual(record.status, WorkingStatus.C_HOUTEI_KYUJITU)

    @patch("sao.core.is_holiday", return_value=True)
    @patch("sao.core.get_employee_hour")
    def test_generate_daily_record_holiday_no_stamps(self, mock_get_employee_hour, mock_is_holiday):
        # 休日出勤なし 打刻が空のレコードを作成するい
        stamps = []
        mock_get_employee_hour.return_value = self.working_hour
        generate_daily_record(stamps, self.employee, self.day)
        record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
        self.assertIsNotNone(record)
        self.assertIsNone(record.clock_in)
        self.assertIsNone(record.clock_out)
        self.assertEqual(record.working_hours_start, None)
        self.assertEqual(record.working_hours_end, None)
        self.assertEqual(record.status, WorkingStatus.C_KYUJITU)

# class TestFinalizeDailyRecord(TestCase):
#     def setUp(self):
#         self.employee = Employee.objects.create(name="Test Employee")
#         self.day = date(2023, 8, 2)

#     @patch("sao.core.EmployeeDailyRecord")
#     def test_skip_if_record_exists(self, mock_EmployeeDailyRecord):
#         # If record exists, should skip and not proceed
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.return_value = True
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             mock_logger.info.assert_called_with("  勤務記録が既に存在しているためスキップします")

#     @patch("sao.core.EmployeeDailyRecord")
#     @patch("sao.core.collect_webstamps")
#     @patch("sao.core.transaction")
#     @patch("sao.core.generate_daily_record")
#     def test_generate_daily_record_none(self, mock_generate_daily_record, mock_transaction, mock_collect_webstamps, mock_EmployeeDailyRecord):
#         # If generate_daily_record returns None, should log and return
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.return_value = False
#         mock_collect_webstamps.return_value = []
#         mock_generate_daily_record.return_value = None
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             mock_logger.info.assert_any_call(f"  打刻データが存在しないためスキップします")

#     @patch("sao.core.EmployeeDailyRecord")
#     @patch("sao.core.DailyAttendanceRecord")
#     @patch("sao.core.collect_webstamps")
#     @patch("sao.core.transaction")
#     @patch("sao.core.generate_daily_record")
#     @patch("sao.core.generate_attendance_record")
#     def test_successful_finalize(self, mock_generate_attendance_record, mock_generate_daily_record, mock_transaction, mock_collect_webstamps, mock_DailyAttendanceRecord, mock_EmployeeDailyRecord):
#         # Normal successful case
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.side_effect = [False, True]
#         mock_collect_webstamps.return_value = MagicMock()
#         mock_collect_webstamps.return_value.__iter__.return_value = [MagicMock(stamp=datetime(2023, 8, 2, 10, 0))]
#         mock_generate_daily_record.return_value = MagicMock()
#         mock_DailyAttendanceRecord.objects.filter.return_value.exists.return_value = True
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             mock_logger.info.assert_any_call("EmployeeDailyRecordを生成しました")
#             mock_logger.info.assert_any_call("DailyAttendanceRecordを生成しました")

#     @patch("sao.core.EmployeeDailyRecord")
#     @patch("sao.core.collect_webstamps")
#     @patch("sao.core.transaction")
#     @patch("sao.core.generate_daily_record")
#     def test_exception_in_transaction(self, mock_generate_daily_record, mock_transaction, mock_collect_webstamps, mock_EmployeeDailyRecord):
#         # Simulate exception in transaction.atomic block
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.return_value = False
#         mock_collect_webstamps.return_value = []
#         mock_generate_daily_record.side_effect = Exception("fail")
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             self.assertTrue(any("切り替え処理に失敗しました" in str(call) for call in mock_logger.error.call_args_list))

#     @patch("sao.core.EmployeeDailyRecord")
#     @patch("sao.core.DailyAttendanceRecord")
#     @patch("sao.core.collect_webstamps")
#     @patch("sao.core.transaction")
#     @patch("sao.core.generate_daily_record")
#     @patch("sao.core.generate_attendance_record")
#     def test_missing_records_after_transaction(self, mock_generate_attendance_record, mock_generate_daily_record, mock_transaction, mock_collect_webstamps, mock_DailyAttendanceRecord, mock_EmployeeDailyRecord):
#         # EmployeeDailyRecord or DailyAttendanceRecord not created after transaction
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.side_effect = [False, False]
#         mock_collect_webstamps.return_value = MagicMock()
#         mock_collect_webstamps.return_value.__iter__.return_value = [MagicMock(stamp=datetime(2023, 8, 2, 10, 0))]
#         mock_generate_daily_record.return_value = MagicMock()
#         mock_DailyAttendanceRecord.objects.filter.return_value.exists.return_value = False
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             mock_logger.error.assert_any_call(f"EmployeeDailyRecordが生成されませんでした: {self.employee} {self.day}")

#     @patch("sao.core.EmployeeDailyRecord")
#     @patch("sao.core.DailyAttendanceRecord")
#     @patch("sao.core.collect_webstamps")
#     @patch("sao.core.transaction")
#     @patch("sao.core.generate_daily_record")
#     @patch("sao.core.generate_attendance_record")
#     def test_stamps_delete_exception(self, mock_generate_attendance_record, mock_generate_daily_record, mock_transaction, mock_collect_webstamps, mock_DailyAttendanceRecord, mock_EmployeeDailyRecord):
#         # stamps.delete() raises exception
#         mock_EmployeeDailyRecord.objects.filter.return_value.exists.side_effect = [False, True]
#         mock_collect_webstamps.return_value = MagicMock()
#         mock_collect_webstamps.return_value.__iter__.return_value = [MagicMock(stamp=datetime(2023, 8, 2, 10, 0))]
#         mock_collect_webstamps.return_value.delete.side_effect = Exception("delete error")
#         mock_generate_daily_record.return_value = MagicMock()
#         mock_DailyAttendanceRecord.objects.filter.return_value.exists.return_value = True
#         with patch("sao.core.logger") as mock_logger:
#             finalize_daily_record(self.employee, self.day)
#             self.assertTrue(any("Web打刻データの削除に失敗しました" in str(call) for call in mock_logger.error.call_args_list))


    # @patch("sao.core.get_employee_hour", side_effect=NoAssignedWorkingHourError)
    # @patch("sao.core.get_clock_in_out")
    # def test_generate_daily_record_no_working_hour(self, mock_get_clock_in_out, mock_get_employee_hour):
    #     # 勤務時間未設定->レコード作成しない
    #     # Setup
    #     stamps = [datetime(2023, 8, 2, 10, 0)]
    #     mock_get_clock_in_out.return_value = Period(stamps[0], None)

    #     # Act
    #     generate_daily_record(stamps, self.employee, self.day)

    #     # Assert
    #     record = EmployeeDailyRecord.objects.filter(employee=self.employee, date=self.day).first()
    #     self.assertIsNone(record)


