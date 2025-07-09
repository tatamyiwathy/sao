# This script checks if a superuser exists in the Django application.


import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sao_proj.settings")
django.setup()

from django.contrib.auth.models import User

if User.objects.filter(is_superuser=True).exists():
    print("✅ Superuser exists")
else:
    print("❌ No superuser found")
    sys.exit(1)