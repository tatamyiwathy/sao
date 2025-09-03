# -*- coding: utf-8 -*-
import datetime
import calendar

from sao import models
from sao import jholiday


def get_last_sunday(date: datetime.date) -> datetime.date:
    """
    引数で渡された日時から直近の日曜日を取得する
    """
    day = date.weekday()
    if day == 6:
        # 日曜日
        return date
    # 直近の日曜日までの日数
    day = -day - 1
    return date + datetime.timedelta(days=day)


def get_next_sunday(d: datetime.date) -> datetime.date:
    """
    直近の次の日曜日
    """
    return d + datetime.timedelta(6 - d.weekday())


def get_first_day(date: datetime.date) -> datetime.date:
    """月初めのdatetime.dateを取得する"""
    year = date.year
    month = date.month
    return datetime.date(year, month, 1)


def get_last_day(date: datetime.date) -> datetime.date:
    """月末のdatetime.dateを取得する"""
    next_month = get_next_month_date(date)
    return next_month - datetime.timedelta(days=1)


def get_next_month_date(date: datetime.date) -> datetime.date:
    """次月のdatetime.dateを取得する"""
    month = date.month + 1
    year = date.year
    if month >= 13:
        month = 1
        year = year + 1
    return datetime.date(year, month, 1)


def get_last_month_date(date: datetime.date) -> datetime.date:
    """先月のdatetime.dateを取得する"""
    month = date.month - 1
    year = date.year
    if month < 1:
        month = 12
        year = year - 1
    return datetime.date(year, month, 1)


def is_workday(date: datetime.date) -> bool:
    """平日チェック"""
    if jholiday.holiday_name(date=date):
        return False

    if date.weekday() >= 5:
        # 土日チェック
        return False

    if is_local_holiday(date):
        return False

    return True


def is_holiday(d: datetime.date) -> bool:
    """休日チェック(土日も含まれる)"""
    return not is_workday(d)


def is_legal_holiday(d: datetime.date) -> bool:
    """6は日曜日"""
    return d.weekday() == 6


def is_saturday(d: datetime.date) -> bool:
    """5は土曜日"""
    return d.weekday() == 5


def is_local_holiday(d: datetime.date) -> bool:
    """公休日チェック"""
    return len(models.Holiday.objects.filter(date=d)) > 0


def count_working_days(date: datetime.date) -> int:
    """所定の勤務日数を数える"""
    begin_day = datetime.date(date.year, date.month, 1)
    end_day = get_next_month_date(begin_day)

    count = 0
    for i in range((end_day - begin_day).days + 1):
        if is_workday(begin_day + datetime.timedelta(days=i)):
            count += 1
    return count


def enumlate_days(date: datetime.date) -> list:
    """月の日付を列挙する"""
    first_day = get_first_day(date)
    last_day = get_last_day(date)

    days = [
        first_day + datetime.timedelta(days=i)
        for i in range((last_day - first_day).days + 1)
    ]
    return days


def monthdays(date: datetime.date) -> int:
    """月の日数を取得する"""
    return calendar.monthrange(date.year, date.month)[1]
