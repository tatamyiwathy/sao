# -*- coding: utf-8 -*-
import datetime

from django import template
from sao import attendance
from sao import utils
from sao import calendar
from sao import utils
from sao.const import Const

register = template.Library()


# hh::mm::ss の ssを削除
@register.filter
def strip_seconds(delta, empty):
    if isinstance(delta, str):
        return empty
    return utils.format_seconds_to_hhmm(delta.total_seconds(), empty)


@register.filter
def color_ifnot(time, color_word):
    # 60秒未満は切り捨て
    if isinstance(time, str):
        return ""
    if time.total_seconds() < 60:
        return ""
    return color_word


@register.filter
def is_saturday(date):
    return calendar.is_saturday(date.date())


@register.filter
def is_holiday(date):
    return calendar.is_holiday(date.date())


@register.filter
def focus_today(date: datetime.date, day: datetime.date) -> str:
    return "success" if date == day else ""


@register.filter
def row_bg_color(attn: attendance.Attendance, today: datetime.date) -> str:
    if attn.date == today:
        return "success"
    elif attn.get_stamp().is_unset():
        return "danger"
    return ""


@register.simple_tag
def missed_stamp_color(left, right):
    """打刻が片方だけの場合に色を付ける"""
    if utils.is_missed_stamp(left, right):
        if left and not right:
            return "red_color"
    return ""


@register.filter
def set_warning_color(attn: attendance.Attendance, key: str) -> str:
    if key in attn.warnings.keys():
        return "danger"
    return ""


@register.filter
def set_any_warning_color(attn: attendance.Attendance) -> str:
    return "danger" if len(attn.warnings.keys()) > 0 else ""


@register.simple_tag
def warning_midnight(time: datetime.time, attn: attendance.Attendance) -> str:
    if attn.night > Const.TD_ZERO:
        return "color:red;"
    return ""


@register.filter
def warning_overtime(attn: attendance.Attendance) -> str:
    if attn.actual_work == Const.TD_ZERO:
        return ""
    return utils.get_overtime_warning(attn.total_overtime)[0]


@register.filter
def tooltip_overtime(attn: attendance.Attendance) -> str:
    if attn.actual_work == Const.TD_ZERO:
        return ""
    return utils.get_overtime_warning(attn.total_overtime)[1]


@register.filter
def overtime_hours(attn: attendance.Attendance) -> str:
    return ""


@register.simple_tag
def tomorrow(date: datetime.date) -> datetime.date:
    return date + datetime.timedelta(days=1)
