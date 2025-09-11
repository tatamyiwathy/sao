import datetime
import sys
from threading import Thread
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.urls import Resolver404, resolve, reverse
from common.utils_for_test import (
    TEST_ADMIN_USER,
    TEST_USER,
    create_client,
    create_employee,
    create_super_user,
    create_user,
)
from sao import calendar, forms, models, utils, views
from sao.core import (
    get_working_hours_by_category,
    calc_actual_working_time,
    adjust_working_hours,
    calc_tardiness,
    NoAssignedWorkingHourError,
    get_daily_webstamps,
)
from sao.const import Const
from sao.working_status import WorkingStatus
from sao.tests.utils import (
    create_working_hours,
    set_office_hours_to_employee,
    create_timerecord,
    create_time_stamp_data,
    create_attendance_record,
)


class FunctionTest(TestCase):
    def test_create_user(self):
        u = create_user()
        self.assertEqual(u.username, TEST_USER["username"])
        self.assertEqual(u.last_name, TEST_USER["last_name"])
        self.assertEqual(u.first_name, TEST_USER["first_name"])
        self.assertFalse(u.is_superuser)

    def test_create_super(self):
        u = create_super_user()
        self.assertTrue(u.is_superuser)

    def test_create_employee(self):
        u = create_user()
        e = create_employee(u)
        self.assertEqual(e.employee_no, TEST_USER["employee_no"])
        self.assertEqual(e.name, TEST_USER["last_name"] + TEST_USER["first_name"])
        self.assertEqual(e.join_date, TEST_USER["join_date"])

    def test_create_employee2(self):
        u = create_user()
        e = create_employee(u, include_overtime_pay=True)
        self.assertEqual(e.employee_no, TEST_USER["employee_no"])
        self.assertEqual(e.name, TEST_USER["last_name"] + TEST_USER["first_name"])
        self.assertEqual(e.join_date, TEST_USER["join_date"])
        self.assertTrue(e.include_overtime_pay)

    def test_create_employee_with_duplicated_enployee_id(self):
        u = create_user()
        e = create_employee(u)

        uu = utils.create_user(username="morokoshi", last="もろこし", first="輪太郎")

        # enployee_idが重複しているので作成に失敗する
        with self.assertRaises(IntegrityError):
            utils.create_employee(
                employee_no=51,
                name="もろこし輪太郎",
                join_date=datetime.date.today(),
                employee_type=models.Employee.TYPE_PERMANENT_STAFF,
                department=models.Employee.DEPT_DEVELOPMENT,
                user=uu,
            )

    def test_create_working_hour(self):
        create_working_hours()
        self.assertTrue(models.WorkingHour.objects.count() > 0)

    def test_create_timerecord(self):
        e = create_employee(create_user())
        a_day = datetime.date(2020, 3, 9)
        stamp = [
            datetime.datetime.combine(a_day, datetime.time(hour=10)),
            datetime.datetime.combine(a_day, datetime.time(hour=20)),
        ]
        working_hours = (
            datetime.datetime.combine(a_day, datetime.time(10, 0)),
            datetime.datetime.combine(a_day, datetime.time(19, 0)),
        )
        r = create_timerecord(
            employee=e, date=a_day, stamp=stamp, working_hours=working_hours
        )
        self.assertTrue(r.is_valid())
        self.assertEqual(r, models.EmployeeDailyRecord.objects.all()[0])


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
            models.Employee.objects.get(employee_no=52).is_manager
        )  # is_manager=True


class UserTest(TestCase):

    def test_user_is_empty(self):
        users = User.objects.all()
        self.assertEqual(users.count(), 0)

    def test_add_user(self):
        create_user()
        users = User.objects.all()
        self.assertEqual(users.count(), 1)


class EmployeeModelTest(TestCase):
    def test_employee_is_invalid(self):
        employee = models.Employee()
        self.assertFalse(employee.is_valid())

    def test_employee_is_valid(self):
        employee = create_employee(create_user(), include_overtime_pay=True)
        self.assertTrue(employee.is_valid())

    def test_employee_database_is_empty(self):
        registerd_employees = models.Employee.objects.all()
        self.assertEqual(registerd_employees.count(), 0)

    def test_entry_employee_to_database(self):
        user = create_user()
        e = create_employee(user, include_overtime_pay=True)
        e.save()

        o = models.Employee.objects.all()
        self.assertEqual(o.count(), 1)

        o = o.exclude(leave_date__lt=datetime.date(2014, 1, 1))
        self.assertEqual(o.count(), 1)

        o = o.exclude(join_date__gt=datetime.date.today())
        self.assertEqual(o.count(), 1)


class TimeRecordTest(TestCase):

    def setUp(self):
        self.employee = create_employee(create_user(), include_overtime_pay=True)

    def test_instanciate(self):
        fromTime = datetime.datetime.now()
        toTime = datetime.datetime.now()
        models.EmployeeDailyRecord(
            date=datetime.date.today(),
            employee=self.employee,
            clock_in=fromTime,
            clock_out=toTime,
        ).save()

        timerecords = models.EmployeeDailyRecord.objects.all()
        self.assertEqual(timerecords.count(), 1)

    def test_omit_seconds(self):
        fromTime = datetime.datetime(2021, 9, 27, 15, 39, 21)
        toTime = datetime.datetime(2021, 9, 27, 15, 42, 30)
        timerecord = models.EmployeeDailyRecord(
            date=datetime.date(2021, 9, 27),
            employee=self.employee,
            clock_in=fromTime,
            clock_out=toTime,
        )
        self.assertNotEqual(fromTime, timerecord.get_clock_in())
        self.assertEqual(
            toTime.replace(second=0, microsecond=0), timerecord.get_clock_out()
        )


class calendarTest(TestCase):

    def test_last_sunday_getter(self):
        # 月曜日のlast_sunday
        today = datetime.date(2017, 1, 2)
        sunday = calendar.get_last_sunday(today)
        self.assertEqual(sunday, datetime.date(2017, 1, 1))

        # 日曜日のlast_sundayは当日が返る
        today = datetime.date(2017, 1, 8)  # 日曜日
        sunday = calendar.get_last_sunday(today)
        self.assertEqual(sunday, datetime.date(2017, 1, 8))

        # 月初めが日曜日、年始めが日曜日
        today = datetime.datetime(2017, 1, 1)
        sunday = calendar.get_last_sunday(today)
        self.assertEqual(sunday, datetime.datetime(2017, 1, 1))

    def test_is_workday(self):
        date = datetime.date(2017, 1, 1)
        self.assertFalse(calendar.is_workday(date))

        date = datetime.date(2017, 1, 4)
        self.assertTrue(calendar.is_workday(date))

        # 2017-1-3は平日
        date = datetime.date(2017, 1, 3)
        self.assertTrue(calendar.is_workday(date))

        # 2017-1-3を休日テーブルに登録
        holiday = models.Holiday(date=date)
        holiday.save()
        self.assertFalse(calendar.is_workday(date))

    def test_get_first_day_and_last_day_in_manth(self):
        date = datetime.date(2018, 4, 5)
        f = calendar.get_first_day(date)
        self.assertEqual(f, datetime.date(2018, 4, 1))
        l = calendar.get_last_day(date)
        self.assertEqual(l, datetime.date(2018, 4, 30))

    def test_get_last_month(self):
        today = datetime.date(2018, 4, 17)
        lastmonth = calendar.get_last_month_date(today)
        self.assertEqual(lastmonth.month, 3)


class HomeTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.client = create_client(TEST_USER)
        create_working_hours()
        create_time_stamp_data(self.employee)

    def test_is_workday(self):
        self.assertFalse(calendar.is_workday(datetime.date(2021, 8, 9)))

    def test_time_record(self):
        query = models.EmployeeDailyRecord.objects.all()
        self.assertTrue(len(query) > 0)

    def test_get_home(self):
        set_office_hours_to_employee(
            self.employee, datetime.date(1901, 1, 1), get_working_hours_by_category("A")
        )

        r = self.client.post("/", {"yearmonth": "2021-08"})

        self.assertEqual(r.status_code, 200)

    def test_post(self):
        set_office_hours_to_employee(
            self.employee, datetime.date(1901, 1, 1), get_working_hours_by_category("A")
        )

        r = self.client.post(
            "/", {"employee": self.employee.id, "yearmonth": "2021-08"}
        )
        self.assertEqual(r.status_code, 200)


class StaffDetailTest(TestCase):

    def test_staff_detail(self):
        u = create_user()
        e = create_employee(u, include_overtime_pay=True)
        c = create_client(TEST_USER)
        self.assertTrue(c)

        create_working_hours()
        w = get_working_hours_by_category("A")
        set_office_hours_to_employee(e, datetime.date(1901, 1, 1), w)

        url = reverse("sao:staff_detail", args=[e.employee_no, 2017, 1])
        r = c.get(url)
        self.assertEqual(r.status_code, 200)


class EmployeeListTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        create_working_hours()
        w = get_working_hours_by_category("A")
        set_office_hours_to_employee(self.employee, datetime.date(1901, 1, 1), w)
        self.client = create_client(TEST_USER)

    def test_employee_list(self):
        r = self.client.get(reverse("sao:employee_list"))
        self.assertEqual(r.status_code, 200)


class ModifyRecordTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.a_day = datetime.date(2020, 3, 9)

    def test_post(self):
        date = datetime.date(2018, 5, 1)
        stamp = [
            datetime.datetime.combine(date, datetime.time(10)),
            datetime.datetime.combine(date, datetime.time(20)),
        ]
        working_hours = (
            datetime.datetime.combine(date, datetime.time(10, 0)),
            datetime.datetime.combine(date, datetime.time(19, 0)),
        )
        t = create_timerecord(
            employee=self.employee, date=date, stamp=stamp, working_hours=working_hours
        )
        c = create_client(TEST_USER)
        self.assertTrue(c)
        params = {
            "clock_in": stamp[0],
            "clock_out": stamp[1],
            "date": date,
            "status": WorkingStatus.C_KINMU,
            "accepted_overtime": False,
            "accepted_overwork_clockin": "",
            "accepted_overwork_clockout": "",
            "remark": "",
        }

        url = reverse("sao:modify_record", args=[t.id, date.year, date.month])
        resp = c.post(url, params)
        self.assertRedirects(resp, reverse("sao:employee_record"))

    def test_post_kekkin(self):
        # 欠勤データの投入
        date = datetime.date(2018, 5, 1)  # 火曜日
        stamp = [
            datetime.datetime.combine(date, datetime.time(10)),
            datetime.datetime.combine(date, datetime.time(20)),
        ]
        working_hours = (
            datetime.datetime.combine(date, datetime.time(10, 0)),
            datetime.datetime.combine(date, datetime.time(19, 0)),
        )
        t = create_timerecord(
            employee=self.employee, date=date, stamp=stamp, working_hours=working_hours
        )
        c = create_client(TEST_USER)

        params = {
            "clock_in": t.clock_in,
            "clock_out": t.clock_out,
            "date": date,
            "status": WorkingStatus.C_KEKKIN,
            "accepted_overtime": False,
        }
        # post(引数つき)
        url = reverse("sao:modify_record", args=[t.id, date.year, date.month])
        resp = c.post(url, params)
        self.assertRedirects(resp, reverse("sao:employee_record"))

        # DBから欠勤データを取得する
        r = models.EmployeeDailyRecord.objects.get(date=date)
        self.assertEqual(r.status, WorkingStatus.C_KEKKIN)
        self.assertNotEqual(r.clock_in, None)  # 打刻はそのまま残る
        self.assertNotEqual(r.clock_out, None)


# class EmployeeRecordTest(TestCase):
#     def setUp(self):
#         self.user = create_user()
#         self.employee = create_employee(self.user, include_overtime_pay=True)
#         create_working_hours()

#         self.a_day = datetime.date(2021, 8, 1)
#         set_office_hours_to_employee(
#             self.employee, self.a_day, get_working_hours_by_category("A")
#         )
#         create_time_stamp_data(self.employee)

#         self.client = create_client(TEST_USER)

#     def test_get(self):
#         with self.assertTemplateUsed("sao/view.html"):
#             response = self.client.get(
#                 "/sao/employee_record/",
#                 {
#                     "employee": self.employee.id,
#                     "year": self.a_day.year,
#                     "month": self.a_day.month,
#                 },
#             )
#         self.assertEqual(response.status_code, 200)

#     def test_post(self):
#         with self.assertTemplateUsed("sao/view.html"):
#             y = str(self.a_day.year)
#             m = ("0" + str(self.a_day.month))[-2:]
#             yearmonth = "%s-%s" % (y, m)
#             response = self.client.post(
#                 f"/sao/employee_record/",
#                 {
#                     "employee": self.employee.id,
#                     "year": self.a_day.year,
#                     "month": self.a_day.month,
#                     "yearmonth": yearmonth,
#                 },
#             )
#         self.assertTrue(response.status_code, 200)
#         soup = BeautifulSoup(response.content, "html.parser")
#         res = soup.find("td", id="work")


class EditEmployeeTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.client = create_client(TEST_USER)

    def test_get(self):
        response = self.client.get("sao/edit_employee/", {"pk": self.employee.pk})
        self.assertTrue(response.status_code, 200)

    def test_post(self):
        data = {
            "employee_no": self.employee.employee_no,
            "name": self.employee.name,
            "payed_holiday": self.employee.payed_holiday,
            "join_date": self.employee.join_date,
            "leave_date": self.employee.leave_date,
            "employee_type": self.employee.employee_type,
            "department": self.employee.department,
            "include_overtime_pay": self.employee.include_overtime_pay,
            "manager": True,
        }

        url = reverse("sao:edit_employee", args=[self.employee.pk])
        response = self.client.post(url, data)
        self.assertTrue(response.status_code, 200)


class OverviewTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.client = create_client(TEST_USER)
        create_working_hours()

    def test_get(self):
        a_day = datetime.date(2020, 3, 9)
        w = get_working_hours_by_category("A")
        set_office_hours_to_employee(self.employee, a_day, w)
        stamp = [
            datetime.datetime.combine(a_day, datetime.time(hour=10)),
            datetime.datetime.combine(a_day, datetime.time(hour=20)),
        ]
        working_hours = (
            datetime.datetime.combine(a_day, datetime.time(10, 0)),
            datetime.datetime.combine(a_day, datetime.time(19, 0)),
        )
        create_timerecord(
            employee=self.employee, date=a_day, stamp=stamp, working_hours=working_hours
        )
        result = self.client.get(
            reverse("sao:attendance_summary"), {"year": a_day.year, "month": 1}
        )
        self.assertTrue(result.status_code, 200)


class StampTest(TestCase):

    def test_get(self):
        u = create_user()
        e = create_employee(u, include_overtime_pay=True)
        c = create_client(TEST_USER)
        r = c.get(reverse("sao:time_clock"))
        self.assertEqual(r.status_code, 200)

    def test_post(self):
        u = create_user()
        e = create_employee(u, include_overtime_pay=True)
        c = create_client(TEST_USER)
        self.assertTrue(c)
        r = c.put(reverse("sao:time_clock"))
        self.assertEqual(r.status_code, 200)


class PermissionTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client = create_client(TEST_USER)
        self.data = {
            "id": str(self.user.id),
            "is_staff": False,
            "enable_view_temporary_staff_record": False,
            "enable_view_outsource_staff_record": False,
            "enable_view_dev_staff_record": False,
            "enable_view_detail": False,
            "enable_regist_event": False,
            "enable_add_staff": False,
        }

    def test_model_instanciate(self):
        instance = models.Permission.objects.get(user__username="foobar")
        self.assertFalse(instance.user.is_staff)

    def test_view(self):
        r = self.client.get(reverse("sao:permission"))
        self.assertEqual(r.status_code, 200)

        r = self.client.get(reverse("sao:modify_permission", args=[self.user.id]))
        self.assertEqual(r.status_code, 200)

    def test_post(self):
        response = self.client.post(
            reverse("sao:modify_permission", args=[self.user.id]), self.data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Permission.objects.count(), 1)

        permission = models.Permission.objects.get()
        self.assertTrue(permission is not None)
        self.assertEqual(permission.user, self.user)

        form = forms.ModifyPermissionForm(
            {
                "is_staff": permission.user.is_staff,
                "enable_view_temporary_staff_record": permission.enable_view_temporary_staff_record,
                "enable_view_outsource_staff_record": permission.enable_view_outsource_staff_record,
                "enable_view_dev_staff_record": permission.enable_view_dev_staff_record,
                "enable_view_detail": permission.enable_view_dev_staff_record,
                "enable_regist_event": permission.enable_regist_event,
                "enable_add_staff": permission.enable_add_staff,
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_is_invalid(self):
        form = forms.ModifyPermissionForm()
        self.assertFalse(form.is_valid())


# class TimeCalculationTest(TestCase):

#     # 所定労働時間を取得するテスト
#     def setUp(self):
#         self.user = create_user()
#         self.emp = create_employee(self.user, include_overtime_pay=True)
#         self.today = datetime.date(year=2020, month=1, day=23)
#         create_working_hours()

#     def test_tardy(self):
#         """遅刻"""
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         a_day = datetime.date(2019, 3, 9)
#         self.assertTrue(a_day.weekday() == 5)
#         scenarios = [
#             (
#                 a_day,
#                 [datetime.datetime.combine(a_day, datetime.time(9, 54, 00)),
#                  datetime.datetime.combine(a_day, datetime.time(19, 13, 46))],
#                 WorkingStatus.C_HOUTEIGAI_KYUJITU,
#                 Const.TD_ZERO,
#                 "scenario 1",
#             ),  #
#             (
#                 self.today,
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1100),
#                  datetime.datetime.combine(self.today, Const.OCLOCK_1900)],
#                 WorkingStatus.C_KINMU,
#                 Const.TD_1H,
#                 "scenario 2",
#             ),  # 11-19で遅刻1h
#             (
#                 self.today,
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1100), datetime.datetime.combine(self.today, Const.OCLOCK_1500)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
#                 Const.TD_1H,
#                 "scenario 3",
#             ),  # 11-15(後半休・休息あり)で遅刻1h
#             (
#                 self.today,
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1100), datetime.datetime.combine(self.today, Const.OCLOCK_1400)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
#                 Const.TD_1H,
#                 "scenario 4",
#             ),  # 11-15(後半休・休息なし)で遅刻1h
#         ]
#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))
#         for scenario in scenarios:
#             r = create_timerecord(
#                 employee=self.emp,
#                 date=scenario[0],
#                 stamp=scenario[1],
#                 working_hours=working_hours,
#                 status=scenario[2],
#             )
#             tardy = calc_tardiness(r, working_hours[0])
#             self.assertEqual(tardy, scenario[3])

#     def test_early_leaving(self):

#         """早退"""
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )

#         scenarios = [
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_2000)],
#                 WorkingStatus.C_KINMU,
#                 Const.TD_ZERO,
#                 "scanario 1",
#             ),  # 10-20では早退はゼロ
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1800)],
#                 WorkingStatus.C_KINMU,
#                 Const.TD_1H,
#                 "scanario 2",
#             ),  # 10-18では早退は1H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1400)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
#                 Const.TD_ZERO,
#                 "scanario 3",
#             ),  # 10-14(後半休・休息なし)では早退は0
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1300)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
#                 Const.TD_1H,
#                 "scanario 4",
#             ),  # 10-13(後半休・休息なし)では早退は1H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1500)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
#                 Const.TD_ZERO,
#                 "scanario 5",
#             ),  # 10-15（後半休・休息あり）では早退は0
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1400)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
#                 Const.TD_1H,
#                 "scanario 6",
#             ),  # 10-14（後半休・休息あり）では早退は1H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_0000)],
#                 WorkingStatus.C_KINMU,
#                 Const.TD_ZERO,
#                 "scanario 7",
#             ),  # 10-20では早退はゼロ
#         ]

#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))

#         for scenario in scenarios:
#             print(scenario[3])
#             r = create_timerecord(
#                 stamp=scenario[0],
#                 working_hours=working_hours,
#                 date=self.today,
#                 employee=self.emp,
#                 status=scenario[1],
#             )
#             self.assertEqual(r.status, scenario[1])
#             self.assertTrue(r.is_valid_status())
#             attn = create_attendance_record(r)
#             self.assertEqual(attn.early_leave, scenario[2])

#     def test_overtime(self):
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         scenarios = [
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_0930), datetime.datetime.combine(self.today, Const.OCLOCK_1900)],
#                 [],
#                 Const.TD_ZERO,
#                 "scenario 1",
#             ),  # 9:30 - 19:00で超過なし
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1900)],
#                 [],
#                 Const.TD_ZERO,
#                 "scenario 2",
#             ),  # 10:00 - 19:00で超過なし
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1100), datetime.datetime.combine(self.today, Const.OCLOCK_2000)],
#                 [],
#                 Const.TD_ZERO,
#                 "scenario 3",
#             ),  # 11:00 - 20:00で超過なし
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_2000)],
#                 [],
#                 Const.TD_1H,
#                 "scenario 4",
#             ),  # 10:00 - 20:00で1H超過
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1100), datetime.datetime.combine(self.today, Const.OCLOCK_2100)],
#                 [],
#                 Const.TD_1H,
#                 "scenario 5",
#             ),  # 11:00 - 21:00で1H超過
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_2000)],
#                 [Const.OCLOCK_1400, Const.OCLOCK_1500],
#                 Const.TD_ZERO,
#                 "scenario 6",
#             ),  # 10:00 - 20:00外出1Hで超過なし
#         ]

#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))

#         for scenario in scenarios:
#             r = create_timerecord(stamp=scenario[0], working_hours=working_hours, date=self.today, employee=self.emp)
#             if len(scenario[1]) > 0:
#                 # 外出データを登録する
#                 out_time = datetime.datetime.combine(self.today, scenario[1][0])
#                 ret_time = datetime.datetime.combine(self.today, scenario[1][1])
#                 models.SteppingOut(
#                     employee=self.emp, out_time=out_time, return_time=ret_time
#                 ).save()
#             attn = create_attendance_record(r)
#             self.assertEqual(attn.over, scenario[2])

#     def test_work_day(self):
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         """平日,法定外休日"""
#         st = datetime.datetime.combine(self.today, datetime.time(hour=10))
#         ct = datetime.datetime.combine(self.today, datetime.time(hour=19))
#         working_hours = [datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0))]
#         r = create_timerecord(
#             stamp=[st, ct], working_hours=working_hours, date=self.today, employee=self.emp)
#         attn = create_attendance_record(r)
#         self.assertEqual(attn.legal_holiday, Const.TD_ZERO)
#         self.assertEqual(attn.holiday, Const.TD_ZERO)

#     def test_legal_holiday(self):
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         """休日出勤は勤務時間がそのまま労働時間になる"""
#         sunday = calendar.get_last_sunday(self.today)
#         st = datetime.datetime.combine(self.today, datetime.time(hour=10))
#         ct = datetime.datetime.combine(self.today, datetime.time(hour=13))
#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))
#         r = create_timerecord(
#             stamp=[st, ct],
#             date=sunday,
#             employee=self.emp,
#             status=WorkingStatus.C_HOUTEI_KYUJITU,
#             working_hours=working_hours
#         )
#         attn = create_attendance_record(r)
#         self.assertEqual(attn.legal_holiday, Const.TD_3H)

#     def test_holiday(self):
#         """休日はworkが0になる"""
#         set_office_hours_to_employee(
#             self.emp, datetime.date(2019, 1, 1), get_working_hours_by_category("A")
#         )
#         holiday = calendar.get_last_sunday(self.today)
#         self.assertTrue(calendar.is_holiday(holiday))
#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))
#         r = create_timerecord(
#             employee=self.emp,
#             date=holiday,
#             stamp=[None, None],
#             status=WorkingStatus.C_KYUJITU,
#             working_hours=working_hours
#         )
#         attn = create_attendance_record(r)
#         self.assertEqual(attn.clock_in, None)
#         self.assertEqual(attn.clock_out, None)
#         self.assertEqual(attn.actual_work, Const.TD_ZERO)

#     def test_holiday_work(self):
#         """休日出勤 work=TD_9H"""
#         set_office_hours_to_employee(
#             self.emp, datetime.date(2019, 1, 1), get_working_hours_by_category("A")
#         )
#         holiday = calendar.get_last_sunday(self.today)
#         self.assertTrue(calendar.is_holiday(holiday))
#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))
#         stamp=[datetime.datetime.combine(self.today, Const.OCLOCK_1000),
#                datetime.datetime.combine(self.today, Const.OCLOCK_1900)]
#         r = create_timerecord(
#             employee=self.emp,
#             date=holiday,
#             stamp=stamp,
#             status=WorkingStatus.C_HOUTEI_KYUJITU,
#             working_hours=working_hours
#         )
#         attn = create_attendance_record(r)
#         self.assertEqual(attn.actual_work, Const.TD_9H)

#     def test_missing_timestamp(self):
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )
#         sunday = calendar.get_last_sunday(self.today)
#         """休日出勤で打刻わすれ"""
#         st = datetime.datetime.combine(self.today, datetime.time(hour=10))
#         ct = datetime.datetime.combine(self.today, datetime.time(hour=19))
#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))
#         r = create_timerecord(
#             stamp=[ct, None],
#             date=sunday,
#             employee=self.emp,
#             status=WorkingStatus.C_KYUJITU,
#             working_hours=working_hours
#         )
#         r.clock_out = None
#         attn = create_attendance_record(r)
#         self.assertEqual(attn.holiday, Const.TD_ZERO)

#     def test_afternoon_holiday(self):
#         """午後休"""
#         set_office_hours_to_employee(
#             self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
#         )

#         scenarios = [
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1400)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
#                 Const.TD_4H,
#             ),  # 10-14(後半休・休息なし)実働4H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1500)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
#                 Const.TD_5H,
#             ),  # 10-15(後半休・休息なし)実働5H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1500)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
#                 Const.TD_4H,
#             ),  # 10-15（後半休・休息あり）実働4H
#             (
#                 [datetime.datetime.combine(self.today, Const.OCLOCK_1000), datetime.datetime.combine(self.today, Const.OCLOCK_1600)],
#                 WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
#                 Const.TD_5H,
#             ),  # 10-14（後半休・休息あり）実働5H
#         ]

#         working_hours = (datetime.datetime.combine(self.today, datetime.time(10, 0)),
#                             datetime.datetime.combine(self.today, datetime.time(19, 0)))

#         for scenario in scenarios:
#             r = create_timerecord(
#                 stamp=scenario[0],
#                 working_hours=working_hours,
#                 date=self.today,
#                 employee=self.emp,
#                 status=scenario[1],
#             )
#             attn = create_attendance_record(r)
#             self.assertEqual(attn.actual_work, scenario[2])


class ManagerTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.emp = create_employee(self.user, include_overtime_pay=True)

    def test_is_manager(self):
        is_manager = self.emp.is_manager()
        self.assertFalse(is_manager)

        manager = models.Manager(manager=self.emp)
        manager.save()
        is_manager = self.emp.is_manager()
        self.assertTrue(is_manager)


class FixedOverworkTest(TestCase):
    def setUp(self):
        self.day = datetime.date(2021, 9, 6)
        self.user = create_user()
        self.emp = create_employee(self.user, include_overtime_pay=True)
        self.today = datetime.date(year=2020, month=1, day=23)
        create_working_hours()

    def test_overtime(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """残業あり"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=21))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.day,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over, Const.TD_2H)

    def test_over_8h(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """超過時間"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=23))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over_8h, Const.TD_4H)

    def test_no_over_8h(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=19))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over_8h, Const.TD_ZERO)

    def test_night_time(self):

        def make_timedelta(sec: int) -> datetime.timedelta:
            return datetime.timedelta(seconds=sec)

        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """深夜を超えていない"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=19))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.night, Const.TD_ZERO)

        """深夜をオーバー:22:01"""
        ct = datetime.datetime.combine(self.today, datetime.time(hour=22, minute=1))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.night, make_timedelta(60))


# 含み残業がない場合
class NoIncludeOverPayTest(TestCase):
    def setUp(self):
        self.day = datetime.date(2021, 9, 6)
        self.user = create_user()
        self.emp = create_employee(self.user)
        self.today = datetime.date(year=2020, month=1, day=23)
        create_working_hours()

    def test_overtime(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """時間外の打刻でも残業は発生しない"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=21))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.day,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over, Const.TD_ZERO)


"""含み残業が適用されるスタッフの時間外打刻"""


class IncludeOverPayedTest(TestCase):
    def setUp(self):
        self.day = datetime.date(2021, 9, 6)
        self.user = create_user()
        self.emp = create_employee(self.user, include_overtime_pay=True)
        self.today = datetime.date(year=2020, month=1, day=23)
        create_working_hours()

    def test_overtime(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """時間外の打刻でも残業は発生しない"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=21))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.day,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over, Const.TD_2H)

    def test_over_8h(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """８時間超過の計算"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=23))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertEqual(attn.over_8h, Const.TD_4H)

    def test_night_time(self):
        set_office_hours_to_employee(
            self.emp, datetime.date(1900, 1, 1), get_working_hours_by_category("A")
        )
        """深夜をオーバー:22:01"""
        st = datetime.datetime.combine(self.today, datetime.time(hour=10))
        ct = datetime.datetime.combine(self.today, datetime.time(hour=22, minute=1))
        working_hours = (
            datetime.datetime.combine(self.today, datetime.time(10, 0)),
            datetime.datetime.combine(self.today, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[st, ct],
            working_hours=working_hours,
            date=self.today,
            employee=self.emp,
        )
        attn = create_attendance_record(r)
        self.assertNotEquals(attn.night, Const.TD_ZERO)


class HolidayViewTest(TestCase):

    def test_view_holiday(self):
        create_user()
        c = create_client(TEST_USER)
        self.assertTrue(c)
        response = c.get(reverse("sao:holiday_settings"))
        self.assertEqual(response.status_code, 200)

    def test_register_holiday_view(self):
        create_user()
        c = create_client(TEST_USER)

        response = c.post(reverse("sao:holiday_settings"), {"date": "2017-01-01"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(models.Holiday.objects.all()) > 0)

    def test_delete_holiday_view(self):
        create_user()
        c = create_client(TEST_USER)

        holiday = models.Holiday.objects.create(date=datetime.date(2017, 1, 1))
        holiday.save()

        c.get(reverse("sao:delete_holiday", kwargs=dict(id=holiday.pk)))
        self.assertTrue(len(models.Holiday.objects.all()) == 0)


class ThreadTest(TransactionTestCase):
    # Threadを使用してDBをいじるときはTransactionTestCaseを使用する
    def threadmain(self):
        self.assertTrue(models.Foo.objects.all().count() > 0)

    def test(self):
        # オブジェクトを作成する
        models.Foo.objects.create()

        th = Thread(target=self.threadmain)
        th.start()
        th.join()

        self.assertTrue(models.Foo.objects.exists())


class ReadCsvTest(TestCase):
    def test(self):
        with open("test-data/NYUTAISTATE.CSV", "rb") as f:
            sjis_str = f.read()
            utf8_str = sjis_str.decode("shift-jis")
            utf8_lines = utf8_str.split("\n")[:-1]
            items = utf8_lines[0].split(",")
            self.assertEqual(items[0], '"帳票タイトル"')


class LoginTest(TestCase):
    def test_user_login(self):
        create_user()
        c = create_client(TEST_USER)
        r = c.get("/")
        self.assertEqual(TEST_USER["username"], r.context["user"].username)

    def test_admin_login(self):
        create_super_user()
        c = create_client(TEST_ADMIN_USER)
        r = c.get("/")
        username = r.context["user"].username
        self.assertEqual(TEST_ADMIN_USER["username"], username)


class Over6HourTest(TestCase):
    def setUp(self):
        self.day = datetime.date(2020, 1, 21)
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        create_working_hours()

    # 6時間超勤務の時は休息1時間が差し引かれる
    def test_adjust_endtime(self):
        """10-19勤務なら勤務時間が6時間超なので1時間休息する"""
        set_office_hours_to_employee(
            self.employee, datetime.date(1901, 1, 1), get_working_hours_by_category("A")
        )
        working_hours = (
            datetime.datetime.combine(self.day, datetime.time(10, 0)),
            datetime.datetime.combine(self.day, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[
                datetime.datetime.combine(self.day, datetime.time(hour=10)),
                datetime.datetime.combine(self.day, datetime.time(hour=19)),
            ],
            working_hours=working_hours,
            employee=self.employee,
            date=self.day,
        )
        working_hours = adjust_working_hours(r)
        self.assertEqual(working_hours.duration(), Const.TD_9H)
        actual_work = calc_actual_working_time(
            r, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        self.assertEqual(actual_work, Const.TD_8H)

    def test_just_six_hours(self):
        """10-19勤務で16時に早退したら実労働時間は6h 実際は休息1時間を取っているので5hだけどそれは感知しない"""
        set_office_hours_to_employee(
            self.employee, datetime.date(1901, 1, 1), get_working_hours_by_category("A")
        )
        working_hours = (
            datetime.datetime.combine(self.day, datetime.time(10, 0)),
            datetime.datetime.combine(self.day, datetime.time(19, 0)),
        )
        r = create_timerecord(
            stamp=[
                datetime.datetime.combine(self.day, Const.OCLOCK_1000),
                datetime.datetime.combine(self.day, Const.OCLOCK_1600),
            ],
            working_hours=working_hours,
            employee=self.employee,
            date=self.day,
        )
        working_hours = adjust_working_hours(r)
        self.assertEqual(working_hours.end - working_hours.start, Const.TD_9H)
        actual_work = calc_actual_working_time(
            r, working_hours.start, working_hours.end, Const.TD_ZERO
        )
        self.assertEqual(actual_work, Const.TD_6H)

    """
    「後半休（休憩あり）」で勤務時間が６時間を超過していた場合に、休憩時間が２回（２時間分）引かれてしまっています。
    「後半休（休憩あり）」で６時間勤務未満の場合は今のままで大丈夫ですが、６時間を超過していた場合は休憩時間が二重に引かれないように、修正をお願いします。
    
    20/02/18
    ８時間勤務の従業員が半休をとった際に、実務時間が１時間少なく算出されてしまうケースです。
    ６時間を超えない場合は休憩時間が不要なのですが、
    勤務時間が短く休憩時間をとっていない場合でも、一律１時間を引いてしまっているようです。
    
    以前お願いしたのは、後半休（休憩あり）の場合のみでしたが、
    前半休の場合でも１時間少なく計算されていました。
    
    ８時間勤務の場合、半休をとった際の始業と就業時刻は下記の通りです。
    ・前半休…15:00～19:00
    ・後半休（なし）…10:00～14:00
    ・後半休（あり）…10:00～15:00
    """

    def test_calc_actual_working_hours(self):
        """10-19の後半休（あり）で18時終業したら労働時間は7h"""
        set_office_hours_to_employee(
            self.employee, datetime.date(1901, 1, 1), get_working_hours_by_category("A")
        )

        # 打刻データ生成
        t = datetime.date(year=2020, month=1, day=21)
        working_hours = (
            datetime.datetime.combine(self.day, datetime.time(10, 0)),
            datetime.datetime.combine(self.day, datetime.time(19, 0)),
        )
        r = create_timerecord(
            employee=self.employee,
            date=t,
            stamp=[
                datetime.datetime.combine(t, Const.OCLOCK_1000),
                datetime.datetime.combine(t, Const.OCLOCK_1800),
            ],
            status=WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
            working_hours=working_hours,
        )
        working_hour = adjust_working_hours(r)
        self.assertEqual(working_hour.end - working_hour.start, Const.TD_5H)
        self.assertEqual(working_hour.end.time(), Const.OCLOCK_1500)

        # 実働時間
        result = calc_actual_working_time(
            r, working_hour.start, working_hour.end, Const.TD_ZERO
        )
        self.assertEqual(result, Const.TD_7H)

    def test_calc_actual_working_hours_2(self):
        """10-19の後半休（休息あり）4時間勤務"""
        # 打刻データ生成
        t = datetime.date(2020, 1, 21)
        working_hours = (
            datetime.datetime.combine(t, datetime.time(10, 0)),
            datetime.datetime.combine(t, datetime.time(19, 0)),
        )
        r = create_timerecord(
            employee=self.employee,
            date=t,
            stamp=[
                datetime.datetime.combine(t, Const.OCLOCK_1000),
                datetime.datetime.combine(t, Const.OCLOCK_1500),
            ],
            status=WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
            working_hours=working_hours,
        )
        working_hour = adjust_working_hours(r)
        self.assertEqual(working_hour.end - working_hour.start, Const.TD_5H)
        self.assertEqual(working_hour.end.time(), Const.OCLOCK_1500)

        # 実働時間
        result = calc_actual_working_time(
            r, working_hour.start, working_hour.end, Const.TD_ZERO
        )
        self.assertEqual(result, Const.TD_4H)


class WebTimeStampViewTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.employee = create_employee(self.user, include_overtime_pay=True)
        self.client = create_client(TEST_USER)

    def test_view(self):
        response = self.client.post("/webtimestamp/%d/" % self.employee.employee_no)
        self.assertEqual(response.status_code, 200)

    def test_db_entry(self):
        dt = datetime.datetime(2020, 5, 5, 15, 39, 0)
        models.WebTimeStamp(employee=self.employee, stamp=dt).save()
        self.assertTrue(models.WebTimeStamp.objects.all().count() == 1)

        stamps = models.WebTimeStamp.objects.filter(employee=self.employee)
        self.assertTrue(stamps.count() == 1)

    """'
    スタンプを収集
    指定した日付のスタンプを収集できることを確認する
    """

    def test_collect_stamps(self):
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 28, 10, 0, 0)
        ).save()
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 28, 19, 0, 0)
        ).save()
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 29, 10, 0, 0)
        ).save()
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 29, 19, 0, 0)
        ).save()
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 30, 10, 0, 0)
        ).save()
        models.WebTimeStamp(
            employee=self.employee, stamp=datetime.datetime(2020, 4, 30, 19, 0, 0)
        ).save()

        # 4/29のスタンプを収集
        stamps = get_daily_webstamps(self.employee, datetime.date(2020, 4, 29))
        self.assertEqual(len(stamps), 2)  # ２件のスタンプが取得できれば成功


class TestEnumlateDays(TestCase):
    def test_enumlate_days(self):
        date = datetime.date(2022, 1, 1)
        expected_days = [
            datetime.date(2022, 1, i) for i in range(1, 32)
        ]  # January has 31 days
        actual_days = calendar.enumlate_days(date)
        self.assertEqual(actual_days, expected_days)

    def test_enumlate_days_on_leap_year(self):
        date = datetime.date(2024, 2, 1)
        expected_days = [
            datetime.date(2024, 2, i) for i in range(1, 30)
        ]  # 2024年はうるう年なので2月は29日まで
        actual_days = calendar.enumlate_days(date)
        self.assertEqual(actual_days, expected_days)


class UpdateWorkingHoursTest(TestCase):
    def setUp(self):
        # テスト用ユーザーと勤務時間レコードを作成
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")
        self.working_hour = models.WorkingHour.objects.create(
            category="通常勤務", begin_time="09:00", end_time="18:00", is_active=True
        )

    def test_update_working_hours_success(self):
        url = reverse("sao:edit_working_hours", args=[self.working_hour.id])
        data = {
            "category": "早番",
            "begin_time": "08:00",
            "end_time": "17:00",
            "is_active": True,
        }
        response = self.client.post(url, data)
        self.working_hour.refresh_from_db()
        self.assertEqual(response.status_code, 302)  # リダイレクトされる
        self.assertEqual(self.working_hour.category, "早番")
        self.assertEqual(str(self.working_hour.begin_time), "08:00:00")
        self.assertEqual(str(self.working_hour.end_time), "17:00:00")
        self.assertTrue(self.working_hour.is_active)

    # 有効ではないデータで更新しようとした場合
    def test_update_working_hours_invalid(self):
        url = reverse("sao:edit_working_hours", args=[self.working_hour.id])
        data = {
            "category": "",  # 空欄はバリデーションエラー
            "begin_time": "08:00",
            "end_time": "07:00",  # 開始 > 終了はバリデーションエラー
            "is_active": True,
        }
        response = self.client.post(url, data)
        self.working_hour.refresh_from_db()
        # レコードは更新されていない
        self.assertNotEqual(self.working_hour.category, "")
        self.assertEqual(response.status_code, 302)  # エラーでもリダイレクト
