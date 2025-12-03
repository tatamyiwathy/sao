#!/bin/bash

echo "DROP DATABASE if exists sao_db;" > tmp
echo "DROP USER if exists 'saoadmin'@'localhost';" >> tmp
echo "CREATE DATABASE sao_db CHARACTER SET utf8;" >> tmp
echo "CREATE USER 'saoadmin'@'localhost' IDENTIFIED BY 'saoadmin';" >> tmp
echo "GRANT ALL PRIVILEGES ON sao_db.* TO 'saoadmin'@'localhost';" >> tmp
echo "GRANT ALL PRIVILEGES ON test_sao_db.* TO 'saoadmin'@'localhost';" >> tmp


mysql -u root -p < tmp

rm tmp

python manage.py migrate

export DJANGO_SUPERUSER_USERNAME=saoadmin
export DJANGO_SUPERUSER_EMAIL=
export DJANGO_SUPERUSER_PASSWORD=saoadmin
python manage.py createsuperuser --noinput

echo "reset db successfully."