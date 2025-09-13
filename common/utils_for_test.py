# import sao.models
# import sao.utils
import datetime
from django.contrib.auth.models import User
from django.test.client import Client
from sao import models as sao_models
from sao import utils as sao_utils


TEST_USER = {
    "username": "foobar",
    "password": "foobar",
    "first_name": "太郎",
    "last_name": "キャベツ",
    "join_date": datetime.date(2015, 1, 1),
    "leave_date": datetime.date(2099, 12, 31),
    "employee_no": 51,
    "employee_type": sao_models.Employee.TYPE_PERMANENT_STAFF,
    "department": sao_models.Employee.DEPT_DEVELOPMENT,
    "email": "foobar@sample.com",
}

TEST_ADMIN_USER = {
    "username": "administrator",
    "email": "admin@foo.bar",
    "password": "singapore",
}


def create_user() -> User:
    user = sao_utils.create_user(
        username=TEST_USER["username"],
        last=TEST_USER["last_name"],
        first=TEST_USER["first_name"],
        password=TEST_USER["password"],
        email=TEST_USER["email"],
    )
    return user


def create_employee(user, **kwargs) -> sao_models.Employee:

    employee_no = (
        kwargs["employee_no"]
        if "employee_no" in kwargs.keys()
        else TEST_USER["employee_no"]
    )
    return sao_utils.create_employee(
        employee_no=employee_no,
        name=user.last_name + user.first_name,
        join_date=TEST_USER["join_date"],
        employee_type=sao_models.Employee.TYPE_PERMANENT_STAFF,
        department=sao_models.Employee.DEPT_DEVELOPMENT,
        user=user,
    )


def create_super_user() -> User:
    user = User.objects.create_superuser(
        TEST_ADMIN_USER["username"],
        TEST_ADMIN_USER["email"],
        TEST_ADMIN_USER["password"],
    )
    user.is_superuser = True
    user.save()
    return user


def create_client(account) -> Client:
    c = Client()
    user = User.objects.get(username=account["username"])
    c.force_login(user)
    return c
