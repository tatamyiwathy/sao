#!/bin/bash

keep_days=60

if [ ! -d /var/sao-backups ]; then
    mkdir /var/sao-backups
    chown apache.apache /var/sao-backups
fi

cd /var/sao-backups


. /var/www/django/venv/bin/activate

# 保存期間外ファイルを削除
find . -not -mtime -$keep_days -exec rm -f {} \;

d=`date -I`
f=/var/sao-backups/sao-$d.json
python /var/www/django/sao_proj/manage.py dumpdata --indent 2 --exclude auth.permission --exclude contenttypes > $f
