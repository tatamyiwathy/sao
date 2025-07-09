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
    return utils.print_strip_sec(delta.total_seconds(), empty)


@register.filter
def color_ifnot(time, color_word):
    # 60秒未満は切り捨て
    if time.total_seconds() < 60:
        return ""
    return color_word


@register.filter
def is_saturday(date):
    return calendar.is_saturday(date)


@register.filter
def is_holiday(date):
    return calendar.is_holiday(date)


@register.filter
def focus_today(date: datetime.date, day: datetime.date) -> str:
    return "success" if date == day else ""


@register.filter
def row_bg_color(attn: attendance.Attendance, today: datetime.date) -> str:
    if attn.date == today:
        return "success"
    elif attn.is_missing_stamp():
        return "danger"
    return ""


@register.simple_tag
def missed_stamp_color(left, right):
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
    if attn.work == Const.TD_ZERO:
        return ""
    return utils.get_overtime_warning(attn.summed_out_of_time)[0]


@register.filter
def tooltip_overtime(attn: attendance.Attendance) -> str:
    if attn.work == Const.TD_ZERO:
        return ""
    return utils.get_overtime_warning(attn.summed_out_of_time)[1]


@register.filter
def overtime_hours(attn: attendance.Attendance) -> str:
    return ""


@register.simple_tag
def tomorrow(date: datetime.date) -> datetime.date:
    return date + datetime.timedelta(days=1)
