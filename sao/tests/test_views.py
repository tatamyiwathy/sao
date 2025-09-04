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

