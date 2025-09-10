import unittest
import datetime
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from sao import models, utils, core
from common.utils_for_test import (
    create_employee,
    create_user,
)
from sao.tests.utils import (
    create_working_hours,
    set_office_hours_to_employee,
)


class TimeClockViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u = create_user()
        self.e = create_employee(self.u, include_overtime_pay=True)
        self.client.force_login(self.u)

    def test_time_clock_get_renders_stamps(self):
        now = datetime.datetime.now().replace(microsecond=0)
        stamp1 = models.WebTimeStamp.objects.create(employee=self.e, stamp=now)
        stamp2 = models.WebTimeStamp.objects.create(
            employee=self.e, stamp=now - datetime.timedelta(hours=1)
        )
        url = reverse("sao:time_clock")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "foobar")

    def test_time_clock_post_creates_stamp(self):
        url = reverse("sao:time_clock")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.WebTimeStamp.objects.filter(employee=self.e).exists())

    def test_time_clock_stamps_order(self):
        now = datetime.datetime.now().replace(microsecond=0)
        stamp1 = models.WebTimeStamp.objects.create(employee=self.e, stamp=now)
        stamp2 = models.WebTimeStamp.objects.create(
            employee=self.e, stamp=now - datetime.timedelta(hours=2)
        )
        url = reverse("sao:time_clock")
        response = self.client.get(url)
        stamps = response.context["stamps"]
        self.assertGreaterEqual(stamps[0].stamp, stamps[1].stamp)

    def test_time_clock_only_current_employee_stamps(self):
        other_user = utils.create_user(
            username="otheruser", last="", first="", password="pass"
        )
        other_employee = create_employee(other_user, employee_no=52)
        now = datetime.datetime.now().replace(microsecond=0)
        models.WebTimeStamp.objects.create(employee=other_employee, stamp=now)
        models.WebTimeStamp.objects.create(employee=self.e, stamp=now)
        url = reverse("sao:time_clock")
        response = self.client.get(url)
        stamps = response.context["stamps"]
        for stamp in stamps:
            self.assertEqual(stamp.employee, self.e)


class DaySwitchViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u = create_user()
        self.e = create_employee(self.u, include_overtime_pay=True)
        create_working_hours()
        set_office_hours_to_employee(
            self.e, datetime.date(1901, 1, 1), core.get_working_hours_by_category("A")
        )

        self.date = datetime.date.today()
        self.url = reverse("sao:day_switch")
        # Patch utils functions to avoid side effects
        self._get_daily_webstamps = core.get_daily_webstamps
        self._generate_daily_record = core.generate_daily_record
        self._generate_attendance_record = core.generate_attendance_record

    def test_day_switch_post_creates_daily_record(self):
        """日付変更処理がPOSTで呼ばれたとき、EmployeeDailyRecordが作成されること
        (打刻がなくてもEmployeeDailyRecordは生成される)
        """
        response = self.client.post(self.url, {"date": self.date.strftime("%Y-%m-%d")})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"day switch done", response.content)
        self.assertTrue(
            models.EmployeeDailyRecord.objects.filter(
                employee=self.e, date=self.date
            ).exists()
        )
        self.assertTrue(models.DailyAttendanceRecord.objects.all().exists())

    def test_day_switch_get_returns_done(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"day switch done", response.content)
