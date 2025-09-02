from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "スーパーユーザーが存在するか確認します"

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS("スーパーユーザーが存在します"))
        else:
            self.stdout.write(self.style.WARNING("スーパーユーザーは存在しません"))