import requests
import datetime
import csv
import sys
import os

if len(sys.argv) < 2:
    print('reflect-webstamp.py ip-or-host [yyyy-mm-dd]')
    sys.exit(1)

url = 'http://%s/sao/reflect_webstamp/' % sys.argv[1]

target_date = (datetime.datetime.now() - datetime.timedelta(days=1)).date()
if len(sys.argv) == 3:
    target_date = datetime.datetime.strptime(sys.argv[2], '%Y-%m-%d').date()

session = requests.session()
print(session)

try:
    print(target_date)
    response = session.post(url,data={'targetdate': target_date})
    print(response.content)

except requests.exceptions.ConnectionError:
    print("ConnectionError : URL %s" % url)
    sys.exit(1)
