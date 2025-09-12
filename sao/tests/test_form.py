import datetime
from django.test import TestCase
from sao.forms import (
    ModifyRecordForm,
    AddEmployeeForm,
    YearMonthForm,
    WorkingHourAssignForm,
    StaffYearMonthForm,
    ModifyPermissionForm,
    RegisterHolidayForm,
)
from sao.models import Employee, Holiday
from sao.working_status import WorkingStatus
from common.utils_for_test import create_employee, create_user
from sao.tests.utils import (
    create_working_hours,
    set_office_hours_to_employee,
    get_working_hour_by_category,
)


class ModifyRecordFormTest(TestCase):
    def test_valid_form(self):
        form_data = {
            "clock_in": "2022-01-01 09:00:00",
            "clock_out": "2022-01-01 18:00:00",
            "is_overtime_work_permitted": True,
            "status": WorkingStatus.C_KINMU,
        }
        form = ModifyRecordForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        form_data = {
            "clock_in": "2022-01-01 09:00:00",
            "clock_out": "2022-01-01 08:00:00",  # Invalid: clock_out before clock_in
            "is_overtime_work_permitted": True,
            "status": WorkingStatus.C_KINMU,
        }
        form = ModifyRecordForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertFormError(form, None, "出勤時間が退勤時間より後です")
        # self.assertIn(
        #     "残業開始時間が残業終了時間より後です",
        #     form.errors['__all__'],
        # )

    def test_invalid_holiday_form(self):
        form_data = {
            "clock_in": "2022-01-01 09:00:00",
            "clock_out": "2022-01-01 18:00:00",
            "is_overtime_work_permitted": False,
            "status": WorkingStatus.C_KYUJITU,
        }
        form = ModifyRecordForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form, None, "休日に出勤時間または退勤時間が指定されています"
        )


class AddEmproyeeFormTest(TestCase):
    def setUp(self):
        self.params = {
            "employee_no": 51,
            "accountname": "morokoshi",
            "name": "もろこし 輪太郎",
            "join_date": datetime.date.today(),
            "leave_date": datetime.date(2199, 12, 31),
            "type": 0,
            "department": 0,
            "manager": False,
        }

    def test_empty_form(self):
        form = AddEmployeeForm()
        self.assertFalse(form.is_valid())

    def test_posted_form_with_an_error(self):
        params = self.params
        params["name"] = ("もろこし輪太郎",)
        form = AddEmployeeForm(params)
        self.assertFormError(form, None, "姓と名の間に空白を入れてください")

    def test_duplicate_employee_no(self):
        create_employee(create_user(), include_overtime_pay=True)

        employee = Employee.objects.get(employee_no=51)
        self.assertTrue(employee.employee_no == 51)

        form = AddEmployeeForm(self.params)
        self.assertFalse(form.is_valid())
        self.assertFormError(form, None, "社員番号が重複しています")


class YearMonthFormTest(TestCase):

    def test_YearMonthForm(self):
        form = YearMonthForm()
        self.assertFalse(form.is_valid())

        form = YearMonthForm({"yearmonth": datetime.date.today()})
        self.assertTrue(form.is_valid())

        form = YearMonthForm({"yearmonth": "2017-01-31"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["yearmonth"], datetime.date(2017, 1, 31))


class WorkingHourAssignFormTest(TestCase):

    def test_invalid(self):
        form = WorkingHourAssignForm()
        self.assertFalse(form.is_valid())

    def test_valid(self):
        user = create_user()
        employee = create_employee(user, include_overtime_pay=True)
        create_working_hours()
        w = get_working_hour_by_category("A")
        set_office_hours_to_employee(employee, datetime.date.today(), w)

        today = datetime.date(2022, 1, 1)
        form = WorkingHourAssignForm({"date": today, "working_hours": w.pk})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["date"], today)


class StaffYearMonthFormTest(TestCase):

    def test_form_is_invalid(self):
        form = StaffYearMonthForm()
        self.assertFalse(form.is_valid())

    def test_form_is_valid(self):
        employee = create_employee(create_user(), include_overtime_pay=True)
        form = StaffYearMonthForm({"employee": employee.pk, "yearmonth": "2017-02"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["yearmonth"], "2017-02")


class ModifyPermissionFormTest(TestCase):
    def test_form_is_invalid(self):
        form = ModifyPermissionForm()
        self.assertFalse(form.is_valid())

    def test_form_is_valid(self):
        form = ModifyPermissionForm(
            {
                "is_staff": False,
                "enable_view_temporary_staff_record": False,
                "enable_view_outsource_staff_record": False,
                "enable_view_dev_staff_record": False,
                "enable_view_detail": False,
                "enable_regist_event": False,
                "enable_add_staff": False,
            }
        )
        self.assertTrue(form.is_valid())


class RegisterHolidayFromTest(TestCase):

    def test_form_is_invalid(self):
        form = RegisterHolidayForm()
        self.assertFalse(form.is_valid())

    def test_form_is_valid(self):
        form = RegisterHolidayForm({"date": "2017-01-01"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["date"], datetime.date(2017, 1, 1))

    def test_form_save(self):
        form = RegisterHolidayForm({"date": "2017-01-01"})
        form.is_valid()
        form.save()
        self.assertTrue(len(Holiday.objects.all()) > 0)

    def test_duplicate_date(self):
        Holiday.objects.create(date=datetime.date(2017, 1, 1))
        form = RegisterHolidayForm({"date": "2017-01-01"})
        self.assertFalse(form.is_valid())
        # Todo: assertFormErrorの使い方が間違ってる？
        self.assertFormError(form, None, "すでに登録されています")
