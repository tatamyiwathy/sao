import datetime


from django.core.management.base import BaseCommand
from sao.utils import create_employee, create_user
from sao.models import Employee



class Command(BaseCommand):
    help = "Create demo data for employees and users"
    
    def handle(self, *args, **options):


        

        user = create_user("ohtake", "智", "大竹", "ninniku")

        create_employee(
                    employee_no=1,
                    name="大竹 智",
                    join_date=datetime.date(2020, 4, 1),
                    leave_date=datetime.date(2099, 12, 31),
                    payed_holiday=0,
                    employee_type=Employee.TYPE_PERMANENT_STAFF,
                    department=Employee.DEPT_DEVELOPMENT,
                    include_overtime_pay=True,
                    user=user
                )
