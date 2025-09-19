import unittest
import datetime
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from sao import utils, core
from sao.models import (
    Employee,
    DailyAttendanceRecord,
    EmployeeDailyRecord,
    WebTimeStamp,
)
from common.utils_for_test import create_employee, create_user, create_client, TEST_USER
from sao.tests.utils import (
    create_working_hours,
    assign_working_hour,
    get_working_hour_by_category,
    create_timerecord,
    create_attendance_record,
)
from sao.working_status import WorkingStatus


class TimeClockViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u = create_user()
        self.e = create_employee(self.u)
        self.client.force_login(self.u)

    def test_time_clock_get_renders_stamps(self):
        now = datetime.datetime.now().replace(microsecond=0)
        stamp1 = WebTimeStamp.objects.create(employee=self.e, stamp=now)
        stamp2 = WebTimeStamp.objects.create(
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
        self.assertTrue(WebTimeStamp.objects.filter(employee=self.e).exists())

    def test_time_clock_stamps_order(self):
        now = datetime.datetime.now().replace(microsecond=0)
        stamp1 = WebTimeStamp.objects.create(employee=self.e, stamp=now)
        stamp2 = WebTimeStamp.objects.create(
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
        WebTimeStamp.objects.create(employee=other_employee, stamp=now)
        WebTimeStamp.objects.create(employee=self.e, stamp=now)
        url = reverse("sao:time_clock")
        response = self.client.get(url)
        stamps = response.context["stamps"]
        for stamp in stamps:
            self.assertEqual(stamp.employee, self.e)


class DaySwitchViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u = create_user()
        self.e = create_employee(self.u)
        create_working_hours()
        assign_working_hour(
            self.e, datetime.date(1901, 1, 1), get_working_hour_by_category("A")
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
            EmployeeDailyRecord.objects.filter(employee=self.e, date=self.date).exists()
        )
        self.assertTrue(DailyAttendanceRecord.objects.all().exists())

    def test_day_switch_get_returns_done(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"day switch done", response.content)


class AddEmployeeViewTest(TestCase):

    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.client = create_client(TEST_USER)
        self.params = {
            "employee_no": 52,
            "name": "もろこし 輪太郎",
            "join_date": datetime.date.today(),
            "leave_date": datetime.date(2199, 12, 31),
            "type": 0,
            "department": 0,
            "manager": False,
            "accountname": "morokoshi",
            "password": "password123",
            "email": "morokoshi@example.com",
        }
        create_working_hours()

    def test_create_staff_successfully(self):
        response = self.client.post(reverse("sao:add_employee"), self.params)
        self.assertRedirects(response, reverse("sao:employee_list"))

    def test_add_manager_staff(self):
        self.params["manager"] = True
        response = self.client.post(reverse("sao:add_employee"), self.params)
        self.assertRedirects(response, reverse("sao:employee_list"))
        self.assertTrue(
            Employee.objects.get(employee_no=52).is_manager
        )  # is_manager=True


# class ModifyRecordViewTest(TestCase):
#     def setUp(self):
#         self.user = create_user()
#         self.employee = create_employee(self.user)
#         self.a_day = datetime.date(2020, 3, 9)

#     def test_post(self):
#         date = datetime.date(2018, 5, 1)
#         stamp = [
#             datetime.datetime.combine(date, datetime.time(10)),
#             datetime.datetime.combine(date, datetime.time(20)),
#         ]
#         working_hours = (
#             datetime.datetime.combine(date, datetime.time(10, 0)),
#             datetime.datetime.combine(date, datetime.time(19, 0)),
#         )
#         t = create_timerecord(
#             employee=self.employee, date=date, stamp=stamp, working_hours=working_hours
#         )
#         a = create_attendance_record(t)
#         c = create_client(TEST_USER)
#         self.assertTrue(c)
#         params = {
#             "clock_in": stamp[0].time(),
#             "clock_out": stamp[1].time(),
#             "status": WorkingStatus.C_KINMU,
#         }

#         url = reverse("sao:modify_record", args=[a.pk, date.year, date.month])
#         resp = c.post(url, params)
#         self.assertRedirects(resp, reverse("sao:employee_record"))

#     def test_post_kekkin(self):
#         # 欠勤データの投入
#         c = create_client(TEST_USER)

#         a = DailyAttendanceRecord(
#             employee=self.employee,
#             date=self.a_day,
#             clock_in=None,
#             clock_out=None,
#             status=WorkingStatus.C_KEKKIN,
#         )
#         try:
#             a.save()
#         except Exception as e:
#             self.fail(f"Failed to save DailyAttendanceRecord: {e}")
#         params = {
#             "clock_in": None,
#             "clock_out": None,
#             "status": WorkingStatus.C_KEKKIN,
#         }
#         # post(引数つき)
#         url = reverse("sao:modify_record", args=[a.pk, 2025, 9])
#         resp = c.post(url, params)
#         self.assertRedirects(resp, reverse("sao:employee_record"))

from unittest import mock


class ModifyRecordViewMockTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user)
        self.a_day = datetime.date(2020, 3, 9)
        self.client = create_client(TEST_USER)

    @mock.patch("sao.views.get_object_or_404")
    @mock.patch("sao.views.forms.ModifyRecordForm")
    def test_modify_record_post_success(self, mock_form_cls, mock_get_obj):
        # モックレコードとフォーム
        mock_record = mock.Mock(spec=DailyAttendanceRecord)
        mock_record.pk = 123
        mock_record.date = datetime.date(2022, 5, 1)  # ここを追加
        mock_record.employee = self.employee  # ここを追加
        mock_get_obj.return_value = mock_record
        mock_form = mock.Mock()
        mock_form.is_valid.return_value = True
        mock_form.cleaned_data = {
            "clock_in": datetime.datetime(2022, 5, 1, 9, 0),
            "clock_out": datetime.datetime(2022, 5, 1, 18, 0),
            "status": WorkingStatus.C_KINMU,
        }
        mock_form_cls.return_value = mock_form

        url = reverse("sao:modify_record", args=[mock_record.pk, 2022, 5])
        resp = self.client.post(
            url,
            {
                "clock_in": "2022-05-01 09:00",
                "clock_out": "2022-05-01 18:00",
                "status": WorkingStatus.C_KINMU,
            },
        )
        self.assertEqual(resp.status_code, 302)  # リダイレクト

    @mock.patch("sao.views.get_stepout_record", return_value=None)
    def test_modify_record_post_invalid(self, mock_get_stepout):
        time_record = create_timerecord(
            employee=self.employee,
            date=self.a_day,
            stamp=[
                datetime.datetime.combine(self.a_day, datetime.time(10, 0)),
                datetime.datetime.combine(self.a_day, datetime.time(20, 0)),
            ],
            working_hours=(
                datetime.datetime.combine(self.a_day, datetime.time(10, 0)),
                datetime.datetime.combine(self.a_day, datetime.time(19, 0)),
            ),
            status=WorkingStatus.C_KINMU,
        )
        attendance_record = create_attendance_record(time_record)

        url = reverse("sao:modify_record", args=[attendance_record.pk, 2022, 5])
        resp = self.client.post(
            url,
            {
                "clock_in": "",
                "clock_out": "2020-03-09 18:00",
                "status": WorkingStatus.C_KINMU,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["form"].is_valid())

    @mock.patch("sao.views.get_stepout_record", return_value=None)
    def test_modify_record_with_holiday_status(self, mock_get_stepout):
        time_record = create_timerecord(
            employee=self.employee,
            date=self.a_day,
            stamp=[
                datetime.datetime.combine(self.a_day, datetime.time(10, 0)),
                datetime.datetime.combine(self.a_day, datetime.time(20, 0)),
            ],
            working_hours=(
                datetime.datetime.combine(self.a_day, datetime.time(10, 0)),
                datetime.datetime.combine(self.a_day, datetime.time(20, 0)),
            ),
            status=WorkingStatus.C_KYUJITU,
        )
        attendance_record = create_attendance_record(time_record)

        url = reverse("sao:modify_record", args=[attendance_record.pk, 2022, 5])
        resp = self.client.post(
            url,
            {
                "clock_in": datetime.datetime(2022, 5, 1, 10, 0),
                "clock_out": datetime.datetime(2022, 5, 1, 20, 0),
                "status": WorkingStatus.C_KYUJITU,
            },
        )
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertIn(
            f"区分「休日」に出勤時間または退勤時間が指定されています",
            form.errors["__all__"],
        )
