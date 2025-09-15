import datetime
from django.test import TestCase
from sao.attendance import Attendance
from sao.models import DailyAttendanceRecord
from sao.const import Const
from sao.working_status import WorkingStatus
from common.utils_for_test import create_employee, create_user


class AttendanceTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, employee_no=1)

    def test_attendance_is_invalid(self):
        """ """
        attn = Attendance(date=None, employee=self.employee)  # type: ignore
        self.assertFalse(attn.is_valid())

        attn = Attendance(date=datetime.datetime(2024, 6, 1), employee=self.employee)
        self.assertFalse(attn.is_valid())

    def test_instantiate_attendance_from_daily_record(self):
        """ """

        ar = DailyAttendanceRecord(
            clock_in=datetime.datetime(2024, 6, 1, 9, 0),
            clock_out=datetime.datetime(2024, 6, 1, 17, 0),
            working_hours_start=datetime.datetime(2024, 6, 1, 10, 0),
            working_hours_end=datetime.datetime(2024, 6, 1, 19, 0),
            actual_work=Const.TD_ZERO,
            late=Const.TD_ZERO,
            early_leave=Const.TD_ZERO,
            stepping_out=Const.TD_ZERO,
            over=Const.TD_ZERO,
            over_8h=Const.TD_ZERO,
            night=Const.TD_ZERO,
            legal_holiday=Const.TD_ZERO,
            holiday=Const.TD_ZERO,
            remark="",
            status=WorkingStatus.C_KINMU,
        )

        attn = Attendance(
            date=datetime.datetime(2024, 6, 1), employee=self.employee, record=ar
        )

        self.assertTrue(attn.is_valid())
        self.assertEqual(attn.clock_in, ar.clock_in)
        self.assertEqual(attn.clock_out, ar.clock_out)
        self.assertEqual(attn.actual_work, ar.actual_work)
        self.assertEqual(attn.late, ar.late)
        self.assertEqual(attn.early_leave, ar.early_leave)
        self.assertEqual(attn.stepping_out, ar.stepping_out)
        self.assertEqual(attn.over, ar.over)
        self.assertEqual(attn.over_8h, ar.over_8h)
        self.assertEqual(attn.night, ar.night)
        self.assertEqual(attn.legal_holiday, ar.legal_holiday)
        self.assertEqual(attn.holiday, ar.holiday)
        self.assertEqual(attn.remark, ar.remark)
        self.assertEqual(attn.status, ar.status)
