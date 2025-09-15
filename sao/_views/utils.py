import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from sao.core import (
    get_employee_hour,
    NoAssignedWorkingHourError,
    get_working_hour_pre_assign,
)
from sao.models import Employee, WorkingHour


def get_employee_hours_display(employee: Employee) -> WorkingHour | None:
    """設定された勤務時間を取得する

    :param employee: Employeeオブジェクト
    :return: WorkingHourオブジェクト、勤務時間が設定されていない場合はNone
    """
    try:
        return get_employee_hour(employee, datetime.date.today())
    except NoAssignedWorkingHourError:
        # 合流前で勤務時間が取得できない
        try:
            return get_working_hour_pre_assign(employee).working_hours
        except ValueError:
            return None


def get_employee_by_user(user: User) -> Employee | None:
    try:
        return Employee.objects.get(user=user)
    except ObjectDoesNotExist:
        return None
