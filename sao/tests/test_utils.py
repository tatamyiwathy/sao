import datetime
from django.db.models import Sum
from django.test import TestCase
from sao.utils import setup_sample_data as utils_setup_sample_data
from common.utils_for_test import create_user
from sao.models import Employee, DailyAttendanceRecord
from sao.const import Const


class SetupSampleDataTest(TestCase):
    def test_setup_sample_data(self):
        utils_setup_sample_data()

        # actual_work = DailyAttendanceRecord.objects.aggregate(
        #     actual_work=Sum("actual_work")
        # )
        # print(actual_work)

        attn = DailyAttendanceRecord.objects.filter(date=datetime.date(2021, 8, 2))
        self.assertEqual(attn.first().actual_work, Const.TD_6H)
        self.assertEqual(attn.last().late, Const.TD_2H)
