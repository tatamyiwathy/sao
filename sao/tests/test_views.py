import unittest
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from sao import models, utils
import datetime
from common.utils_for_test import (
    TEST_ADMIN_USER,
    TEST_USER,
    create_client,
    create_employee,
    create_super_user,
    create_user,
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
        stamp2 = models.WebTimeStamp.objects.create(employee=self.e, stamp=now - datetime.timedelta(hours=1))
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
        stamp2 = models.WebTimeStamp.objects.create(employee=self.e, stamp=now - datetime.timedelta(hours=2))
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
        self.e.join_date = datetime.date(2020, 1, 1)
        self.e.leave_date = datetime.date(2099, 12, 31)
        self.e.save()
        self.date = datetime.date.today()
        self.url = reverse("sao:day_switch")
        # Patch utils functions to avoid side effects
        self._collect_webstamp = utils.collect_webstamp
        self._generate_daily_record = utils.generate_daily_record
        self._generate_attendance_record = utils.generate_attendance_record
        utils.collect_webstamp = lambda employee, date: []
        utils.generate_daily_record = lambda stamps, employee, date: models.EmployeeDailyRecord.objects.create(employee=employee, date=date)
        utils.generate_attendance_record = lambda record: None

    def tearDown(self):
        utils.collect_webstamp = self._collect_webstamp
        utils.generate_daily_record = self._generate_daily_record
        utils.generate_attendance_record = self._generate_attendance_record

    def test_day_switch_post_creates_daily_record(self):
        response = self.client.post(self.url, {"date": self.date.strftime("%Y-%m-%d")})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"day switch done", response.content)
        self.assertTrue(models.EmployeeDailyRecord.objects.filter(employee=self.e, date=self.date).exists())

    def test_day_switch_post_deletes_existing_daily_record(self):
        # Create an existing record
        models.EmployeeDailyRecord.objects.create(employee=self.e, date=self.date)
        response = self.client.post(self.url, {"date": self.date.strftime("%Y-%m-%d")})
        self.assertEqual(response.status_code, 200)
        # Should only be one record after switch
        self.assertEqual(models.EmployeeDailyRecord.objects.filter(employee=self.e, date=self.date).count(), 1)

    def test_day_switch_post_raises_if_multiple_records(self):
        # Patch generate_daily_record to create two records
        def create_two_records(stamps, employee, date):
            models.EmployeeDailyRecord.objects.create(employee=employee, date=date)
            models.EmployeeDailyRecord.objects.create(employee=employee, date=date)
        utils.generate_daily_record = create_two_records
        with self.assertRaises(Exception) as cm:
            self.client.post(self.url, {"date": self.date.strftime("%Y-%m-%d")})
        self.assertIn("同日に複数の勤務記録が存在しています", str(cm.exception))

    def test_day_switch_get_returns_done(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"day switch done", response.content)


