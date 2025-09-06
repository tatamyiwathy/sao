import datetime
from django.core.management.base import BaseCommand
from sao import models

class Command(BaseCommand):
    help = "テスト用のタイムスタンプを追加します"

    def handle(self, *args, **options):

        employee_id = options["employee"]
        if not employee_id:
            self.stdout.write(self.style.ERROR("従業員IDを指定してください。"))
            return

        s_date = options["date"].replace('-', '/')
        date = datetime.datetime.strptime(options["date"], "%Y/%m/%d").date() if options["date"] else datetime.date.today()

        employee = models.Employee.objects.get(id=employee_id)
        if not employee:
            self.stdout.write(self.style.ERROR(f"従業員ID {employee_id} が見つかりません。"))
            return
        
        models.WebTimeStamp.objects.create(
            employee=employee,
            stamp=datetime.datetime.combine(date, datetime.time(10, 0))
        )
        models.WebTimeStamp.objects.create(
            employee=employee,
            stamp=datetime.datetime.combine(date, datetime.time(19, 0))
        )


    def add_arguments(self, parser):
        parser.add_argument('--employee', nargs='?', default='', type=int)
        parser.add_argument('--date', nargs='?', default='', type=str)
