# -*- coding: utf-8 -*-

# argv[1] host
# argv[2] csv dir/scv file
# argv[3] date

import requests
import datetime
import csv
import sys
import os
import logging


def find_stamp(employee, stamps):
    for stamp in stamps:
        if "card_no" in employee.keys() and employee["card_no"] == stamp["cardno"]:
            return stamp
    return None


def find_employee_card(cards, employee):
    for card in cards:
        if card["employee_no"] == employee["employee_no"]:
            return card
    return None


logging.basicConfig(level=logging.INFO)
logging.info("start post-stamp")

if len(sys.argv) < 3:
    print("post-stamps.py host csv-directory/file [date:yymmdd]")
    sys.exit(1)

date = sys.argv[3] if len(sys.argv) > 3 else None


url = "http://%s/sao/" % sys.argv[1]
post_record_api = url + "post_stamp/"

stampdate = None
# csv_file_name = sys.argv[2]
# if os.path.isdir(csv_file_name):
#     if date:
#         stampdate = datetime.datetime.strptime(date,'%Y%m%d')
#         csv_file_name = '%s/Site%s.csv' % (csv_file_name, date)
#     else:
#         today = datetime.datetime.now()
#         stampdate = today - datetime.timedelta(days=1)
#         csv_file_name = '%s/Site%s.csv' % (csv_file_name, stampdate.strftime('%Y%m%d'))
# else:
#     basename = os.path.basename(csv_file_name)
#     stampdate = datetime.datetime.strptime(basename, 'Site%Y%m%d.csv')
if date:
    stampdate = datetime.datetime.strptime(date, "%Y%m%d")
else:
    today = datetime.datetime.now()
    stampdate = today - datetime.timedelta(days=1)

# カード情報取得
try:
    response = requests.get("http://%s/sao/get_employee_json" % sys.argv[1])
except Exception:
    exit(1)


employees = response.json()


# スタンプ配列生成
stamps = []
# with open(csv_file_name, encoding='ms932') as csvfile:
#     for l in csv.reader(csvfile, delimiter=',', doublequote=False,
#                         lineterminator='\r\n'):
#         stamps.append({'cardno': int(
#             l[0]), 'begin': l[2], 'close': l[3], 'date': stampdate.date()})

# スタンプ投入
for employee in employees:
    stamp = find_stamp(employee, stamps)
    if not stamp:
        stamp = {
            "begin": "",
            "close": "",
            "date": stampdate.date(),
            "employee_no": employee["employee_no"],
        }
    else:
        stamp["employee_no"] = employee["employee_no"]

    # logging.info("%s" % stamp)
    try:
        response = requests.session().post(post_record_api, data=stamp)
    except Exception:
        exit(1)

    # logging.info("status_code = %d" % response.status_code)
    # print(response.text)

    # if 'result' not in response.text:
    #     print("Error ")
    #     sys.exit(1)

logging.info("Success")
