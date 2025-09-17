import datetime
from django.db.models import Sum
from django.test import TestCase
from sao.utils import setup_sample_data as utils_setup_sample_data
from common.utils_for_test import create_user
from sao.models import Employee, DailyAttendanceRecord
from sao.const import Const
from sao.working_status import WorkingStatus
from sao.calendar import is_holiday


class SetupSampleDataTest(TestCase):
    def setUp(self) -> None:
        pass

    def test_setup_sample_data(self):
        utils_setup_sample_data()

        # actual_work = DailyAttendanceRecord.objects.aggregate(
        #     actual_work=Sum("actual_work")
        # )
        # print(actual_work)

        attn = DailyAttendanceRecord.objects.filter(
            date=datetime.date(2021, 8, 2)
        ).first()
        if attn:
            # 実労働時間、遅刻時間が計算されていること
            self.assertEqual(attn.actual_work, Const.TD_6H)
            self.assertEqual(attn.late, Const.TD_3H)

        attn = DailyAttendanceRecord.objects.filter(
            date=datetime.date(2021, 8, 3)
        ).first()
        if attn and attn.clock_in:
            # 打刻が補正されていること
            self.assertEqual(attn.clock_in.time(), datetime.time(10, 0))
            self.assertEqual(attn.actual_work, Const.TD_9H)
            self.assertEqual(attn.over, Const.TD_1H)

        attn = DailyAttendanceRecord.objects.filter(
            date=datetime.date(2021, 8, 23)
        ).first()
        if attn and attn.working_hours_start and attn.working_hours_end:
            # 休日出勤が計算されていること
            self.assertEqual(attn.clock_in, None)
            self.assertEqual(attn.clock_out, None)
            self.assertEqual(attn.working_hours_start.time(), datetime.time(10, 0))
            self.assertEqual(attn.working_hours_end.time(), datetime.time(19, 0))
            self.assertEqual(attn.actual_work, Const.TD_ZERO)
            self.assertEqual(attn.status, WorkingStatus.C_KEKKIN)

        attn = DailyAttendanceRecord.objects.filter(
            date=datetime.date(2021, 8, 24)
        ).first()
        if attn:
            # 早退が計算されていること
            self.assertEqual(attn.early_leave, datetime.timedelta(seconds=1440))  # 24分
            self.assertEqual(
                attn.actual_work, Const.TD_8H - datetime.timedelta(seconds=1440)
            )  # 7時間36分

    def test_when_holiday(self):
        self.assertTrue(is_holiday(datetime.date(2021, 8, 21)))

        attn = DailyAttendanceRecord.objects.filter(
            date=datetime.date(2021, 8, 21)
        ).first()
        if attn:
            # 休日出勤が計算されていること
            self.assertEqual(attn.working_hours_start, attn.clock_in)
            self.assertEqual(attn.working_hours_end, attn.clock_out)
