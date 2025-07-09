#!/bin/bash

cd /var/www/django
. venv/bin/activate
systemctl stop httpd
python sao_proj/manage.py dumpdata --exclude auth.permission --exclude contenttypes > sao-deploy-backup.json
rm -rf sao_proj
svn export http://10gallon/repos/sao/trunk sao_proj
cd sao_proj
chmod 600 keys/id_rsa
mkdir media/avatar
cp -f conf.d/* /etc/httpd/conf.d
cp -r tools/deploy-sao.sh /var/www/django
cp -r rsyslog.d/sao.conf /etc/rsyslog.d/sao.conf
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
cd ..
chown -R apache.apache sao_proj
systemctl start httpd
rm sao-deploy-backup.json
rm /etc/cron.daily/sao-daily-task.sh
ln -s /var/www/django/sao_proj/tools/sao-daily-task.sh /etc/cron.daily/sao-daily-task.sh
systemctl restart rsyslog

