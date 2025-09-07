import unittest
import datetime
from django.contrib.auth.models import User
from sao.models import Employee, EmployeeDailyRecord, DailyAttendanceRecord

class DailyAttendanceRecordModelTest(unittest.TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.employee = Employee.objects.create(
            employee_no=100,
            name="Unit Test Employee",
            payed_holiday=5,
            join_date=datetime.date(2022, 1, 1),
            leave_date=datetime.date(2099, 1, 1),
            user=self.user,
        )
        self.time_record = EmployeeDailyRecord.objects.create(
            employee=self.employee,
            date=datetime.date(2024, 6, 1),
            clock_in=datetime.datetime(2024, 6, 1, 9, 0),
            clock_out=datetime.datetime(2024, 6, 1, 18, 0),
        )

    def test_create_minimal_daily_attendance_record(self):
        record = DailyAttendanceRecord.objects.create(
            time_record=self.time_record
        )
        self.assertIsNotNone(record.pk)
        self.assertEqual(record.time_record, self.time_record)
        self.assertIsNone(record.actual_working_time)
        self.assertIsNone(record.late_time)
        self.assertIsNone(record.early_leave)
        self.assertIsNone(record.stepping_out)
        self.assertIsNone(record.over_time)
        self.assertIsNone(record.over_8h)
        self.assertIsNone(record.night_work)
        self.assertIsNone(record.legal_holiday_work)
        self.assertIsNone(record.holiday_work)
        self.assertEqual(record.remark, "")
        self.assertIsNone(record.status)
        record.delete()

    def test_create_full_daily_attendance_record(self):
        record = DailyAttendanceRecord.objects.create(
            time_record=self.time_record,
            clock_in=datetime.datetime(2024, 6, 1, 9, 0),
            clock_out=datetime.date(2024, 6, 1),
            actual_working_time=datetime.timedelta(hours=8),
            late_time=datetime.timedelta(minutes=10),
            early_leave=datetime.timedelta(minutes=5),
            stepping_out=datetime.timedelta(minutes=30),
            over_time=datetime.timedelta(hours=1),
            over_8h=datetime.timedelta(minutes=30),
            night_work=datetime.timedelta(minutes=20),
            legal_holiday_work=datetime.timedelta(hours=0),
            holiday_work=datetime.timedelta(hours=0),
            remark="Test remark",
            status=1,
        )
        self.assertEqual(record.clock_in, datetime.datetime(2024, 6, 1, 9, 0))
        self.assertEqual(record.clock_out, datetime.date(2024, 6, 1))
        self.assertEqual(record.actual_working_time, datetime.timedelta(hours=8))
        self.assertEqual(record.late_time, datetime.timedelta(minutes=10))
        self.assertEqual(record.early_leave, datetime.timedelta(minutes=5))
        self.assertEqual(record.stepping_out, datetime.timedelta(minutes=30))
        self.assertEqual(record.over_time, datetime.timedelta(hours=1))
        self.assertEqual(record.over_8h, datetime.timedelta(minutes=30))
        self.assertEqual(record.night_work, datetime.timedelta(minutes=20))
        self.assertEqual(record.legal_holiday_work, datetime.timedelta(hours=0))
        self.assertEqual(record.holiday_work, datetime.timedelta(hours=0))
        self.assertEqual(record.remark, "Test remark")
        self.assertEqual(record.status, 1)
        record.delete()
        
    def tearDown(self):
        self.time_record.delete()
        self.employee.delete()
        self.user.delete()