import sys
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "スーパーユーザーが存在するか確認します"

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS("is_exists_superuser: スーパーユーザーが存在します")
            )
            sys.exit(0)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "is_exists_superuser: スーパーユーザーは存在しません"
                )
            )
            sys.exit(1)
