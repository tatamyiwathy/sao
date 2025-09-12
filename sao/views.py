import csv
import datetime
import itertools
import re
import json
import logging
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from sao import core, forms, models
from sao.calendar import (
    get_first_day,
    get_last_day,
    is_holiday,
    get_next_month_date,
    get_last_sunday,
    get_next_sunday,
)
from sao.exceptions import (
    NoAssignedWorkingHourError,
    AnomalyTimeRecordError,
)
from sao.core import (
    get_employee_hour,
    get_working_hour_tobe_assign,
    get_day_switch_time,
    normalize_to_business_day,
    get_monthly_attendance,
    get_attendance_in_period,
    fill_missiing_attendance,
    finalize_daily_record,
)
from sao.const import Const
from sao.working_status import WorkingStatus
from sao.utils import (
    tally_attendances,
    tally_over_work_time,
    get_employee_type_display,
    get_department_display,
    make_web_stamp_string,
    get_employee_status_display,
    attention_overtime,
    is_empty_stamp,
    is_missed_stamp,
    create_user,
    create_employee,
    format_seconds_to_hhmmss,
)
from sao.utils import setup_sample_data as utils_setup_sample_data

from sao.period import Period
from sao.attendance import Attendance

logger = logging.getLogger("sao")  # views専用のロガー


@login_required
def home(request):
    """
    ■マイページ
    """

    def list_warnings(attn: Attendance, today: datetime.date) -> dict:
        """警告をリストアップする"""
        warnings = {}
        if attn.remark:
            # 処理済み
            return {}

        if (today - attn.date.date()).days < 2:
            # 猶予期間
            return {}

        if is_missed_stamp(attn.clock_in, attn.clock_out):
            # 打刻が片方だけ
            warnings["missed_stamp"] = True
        if not is_holiday(attn.date.date()) and is_empty_stamp(
            attn.clock_in, attn.clock_out
        ):
            # 平日で打刻なし
            warnings["nostamp_workday"] = True
        if attn.legal_holiday > Const.TD_ZERO:
            # 法廷休日で打刻あり
            warnings["legal_holiday"] = True
        if attn.holiday > Const.TD_ZERO:
            # 休日で打刻あり
            warnings["holiday"] = True
        if attn.late > Const.TD_ZERO:
            # 遅刻
            warnings["tardy"] = True
        if attn.actual_work > Const.TD_ZERO:
            # 早退
            warnings["leave_early"] = True
        if attn.night > Const.TD_ZERO:
            # 深夜
            warnings["midnight_work"] = True

        if attn.stepping_out > Const.TD_ZERO:
            # 外出
            warnings["steppingout"] = True

        return warnings

    def is_need_overwork_notification(attn: Attendance, today: datetime.date) -> bool:
        """残業の通知が必要かどうかを判定する"""
        if attn.total_over <= datetime.timedelta(hours=25):
            return False

        if attn.remark:
            # 処理済み
            return False

        if (today - attn.date).days < 2:
            # 猶予期間
            return False

        if is_holiday(attn.date) and is_empty_stamp(attn.clock_in, attn.clock_out):
            return False

        return True

    def set_warning_message(
        attendances: list[Attendance], view_date: datetime.date, today: datetime.date
    ) -> list:
        """警告メッセージを設定する"""
        for attn in attendances:
            w = list_warnings(attn, today)
            if len(w.keys()) > 0:
                attn.warnings = w
                messages.warning(
                    request,
                    "%d/%d 届出の提出がされていない可能性があります。勤務データをご確認の上、届出の提出を行ってください"
                    % (attn.date.month, attn.date.day),
                )

            if employee.include_overtime_pay and is_need_overwork_notification(
                attn, today
            ):
                messages.warning(
                    request,
                    "%d/%d 残業が25時間を越えました。速やかに管理者へ届け出を行ってください。"
                    % (attn.date.month, attn.date.day),
                )

        if (
            employee.include_overtime_pay
            and (attendances[-1].total_over <= datetime.timedelta(hours=25))
            and (attendances[-1].total_over > datetime.timedelta(hours=23))
        ):
            if view_date.year == today.year and view_date.month == today.month:
                messages.warning(
                    request,
                    "残業時間が25時間を越えそうです。25時間を越えないようにするか、超過手続きを管理者に届け出る準備をお願いします。",
                )

        return attendances

    def make_view(
        employee: models.Employee, view_date: datetime.date, today: datetime.date
    ):
        """勤務者のマイページを作成する"""
        first_day = datetime.datetime.combine(
            get_first_day(view_date), datetime.time(0, 0)
        )
        next_month_first_day = datetime.datetime.combine(
            get_last_day(view_date) + datetime.timedelta(days=1), datetime.time(0, 0)
        )
        period = Period(first_day, next_month_first_day)
        # 月次集計
        attendances = get_attendance_in_period(
            employee, period.start.date(), period.end.date()
        )
        # 欠損日補完
        attendances = fill_missiing_attendance(employee, period, attendances)
        # 時間外労働時間を集計する
        attendances[-1].total_over = tally_over_work_time(view_date.month, attendances)
        # messageで警告を表示する
        if employee.employee_type == models.Employee.TYPE_PERMANENT_STAFF:
            attendances = set_warning_message(attendances, view_date, today)

        # 集計する
        summed_up = tally_attendances(attendances)

        # 時間外勤務についての警告
        warn_class, warn_title = attention_overtime(summed_up["out_of_time"])

        # 計算結果をまるめる
        rounded = core.round_attendance_summary(summed_up)

        daycount = core.count_days(attendances, view_date)

        return render(
            request,
            "sao/attendance_detail.html",
            {
                "form": form,
                "duty_result": attendances,
                "total_result": summed_up,
                "rounded_result": rounded,
                "employee": employee,
                "year": view_date.year,
                "month": view_date.month,
                "daycount": daycount,
                "office_hours": office_hours,
                "fromTime": fromTime,
                "toTime": toTime,
                "mypage": True,
                "warn": warn_class,
                "today": today,
            },
        )

    # 勤務者オブジェクトを取得する
    try:
        employee = models.Employee.objects.get(user=request.user)
    except ObjectDoesNotExist:
        # Employeeが存在しない場合（スーパーユーザー）
        return render(
            request,
            "sao/attendance_detail_empty.html",
            {"message": "スーパーユーザーでログイン中"},
        )

    # 今日の出退勤時刻を取得する
    today = core.get_today()

    # 設定された勤務時間を取得する
    try:
        office_hours = get_employee_hour(employee, datetime.date.today())
    except NoAssignedWorkingHourError:
        # 合流前で勤務時間が取得できない
        try:
            office_hours = get_working_hour_tobe_assign(employee).working_hours
        except ValueError:
            attendaces = tally_attendances([])
            rounded = core.round_attendance_summary(attendaces)
            return render(
                request,
                "sao/attendance_detail.html",
                {
                    "employee": employee,
                    "year": today.year,
                    "month": today.month,
                    "total_result": attendaces,
                    "rounded_result": rounded,
                    "today": today,
                    "mypage": True,
                },
            )

    # 本日の打刻を取得する
    (fromTime, toTime) = make_web_stamp_string(employee, today)

    # 表示月を決定する
    if request.method == "POST":
        form = forms.YearMonthForm(request.POST)
        if form.is_valid():
            date_on_view = datetime.datetime.strptime(
                form.cleaned_data["yearmonth"], "%Y-%m"
            ).date()
            return make_view(employee, date_on_view, today)

    """GET"""
    form = forms.YearMonthForm()
    viewdate = datetime.date.today()
    if "yearmonth" in request.GET:
        viewdate = datetime.datetime.strptime(request.GET["yearmonth"], "%Y-%m").date()
    if "today" in request.GET:
        today = datetime.datetime.strptime(request.GET["today"], "%Y-%m-%d").date()
        viewdate = datetime.date(today.year, today.month, 1)

    return make_view(employee, viewdate, today)


def staff_detail(request, employee, year, month):
    """
    ■勤務実績ー詳細
    """
    employee = models.Employee.objects.get(employee_no=employee)
    from_date = datetime.datetime.combine(
        datetime.date(year=year, month=month, day=1), datetime.time(0, 0)
    )
    to_date = datetime.datetime.combine(
        get_next_month_date(from_date), datetime.time(0, 0)
    ) + datetime.timedelta(days=1)
    period = Period(from_date, to_date)

    office_hours = get_employee_hour(employee, datetime.date.today())

    # 期間
    attendances = get_attendance_in_period(employee, from_date, to_date)
    # 欠損日補完
    attendances = fill_missiing_attendance(employee, period, attendances)
    total_overtime = tally_over_work_time(from_date.month, attendances)

    summed_up = tally_attendances(attendances)
    rounded_result = core.round_attendance_summary(summed_up)

    daycount = core.count_days(attendances, from_date)

    return render(
        request,
        "sao/attendance_detail.html",
        {
            "duty_result": attendances,
            "total_result": summed_up,
            "rounded_result": rounded_result,
            "employee": employee,
            "year": from_date.year,
            "month": from_date.month,
            "daycount": daycount,
            "office_hours": office_hours,
            "mypage": False,
            "today": datetime.date.today(),
        },
    )


@login_required
def del_employee_hour(request, id):
    """
    ■勤務時間の削除ページ
    """
    employee_hour = models.EmployeeHour.objects.get(id=id)
    employee = employee_hour.employee
    content = str(employee_hour)
    employee_hour.delete()

    logger.info("%sが%sを削除した" % (request.user, content))

    return redirect("sao:employee_hour_view", employee_no=employee.employee_no)


@login_required
def employee_hour_view(request, employee_no):
    """
    ■勤務時間適用リストページ
    """
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    if request.method == "POST":
        employee_hour = models.EmployeeHour(employee=employee)
        form = forms.WorkingHourAssignForm(request.POST, instance=employee_hour)
        if form.is_valid():
            date = form.cleaned_data["date"]
            if date < employee.join_date:
                messages.error(request, "入社日以前の日付は設定できません")
            elif not models.EmployeeHour.objects.filter(
                employee=employee, date=date
            ).exists():
                form.save()
                logger.info("%sが%sを追加した" % (request.user, employee_hour))
            else:
                messages.error(request, "すでに設定されています")
    else:
        form = forms.WorkingHourAssignForm(
            instance=employee, initial={"date": datetime.date.today()}
        )
    employee_hours = (
        models.EmployeeHour.objects.filter(employee=employee)
        .filter(date__gte=datetime.date.today())
        .order_by("-date")
    )

    return render(
        request,
        "sao/employee_hour_assign.html",
        {
            "employee": employee,
            "office_hours": employee_hours,
            "form": form,
            "today": datetime.date.today(),
        },
    )


@login_required
def employee_list(request):
    """
    ■社員一覧
    """

    # 正社員数をカウントする
    def count_reglars(employees, is_active):
        cnt = 0
        for emply in employees:
            if (
                emply.user.is_active == is_active
                and emply.employee_type == models.Employee.TYPE_PERMANENT_STAFF
            ):
                cnt += 1
        return cnt

    # 派遣社員数をカウントする
    def count_temporaries(employees):
        cnt = 0
        for emply in employees:
            if emply.employee_type == models.Employee.TYPE_TEMPORARY_STAFF:
                cnt += 1
        return cnt

    # 業務委託をカウントする
    def count_outsources(employees):
        cnt = 0
        for emply in employees:
            if emply.employee_type == models.Employee.TYPE_TEMPORARY_STAFF:
                cnt += 1
        return cnt

    def count_active_staff():
        q = models.Employee.objects.filter(user__is_active=True)
        total = len(q)

        return (
            total,
            len(q.filter(employee_type=models.Employee.TYPE_PERMANENT_STAFF)),
            len(q.filter(employee_type=models.Employee.TYPE_TEMPORARY_STAFF)),
            len(q.filter(employee_type=models.Employee.TYPE_OUTSOURCING_STAFF)),
        )

    def count_whole_staff():
        q = models.Employee.objects.all()
        total = len(q)

        return (
            total,
            len(q.filter(employee_type=models.Employee.TYPE_PERMANENT_STAFF)),
            len(q.filter(employee_type=models.Employee.TYPE_TEMPORARY_STAFF)),
            len(q.filter(employee_type=models.Employee.TYPE_OUTSOURCING_STAFF)),
        )

    hide_deactive_staff = False
    if "filtered" in request.GET:
        hide_deactive_staff = True

    employee_list = []

    employees = models.Employee.objects.all()
    enrolled_staff = employees.filter(user__is_active=True).order_by("employee_no")
    retired_staff = employees.filter(user__is_active=False).order_by("employee_no")
    employees = itertools.chain(enrolled_staff, retired_staff)

    num_active_staff = count_active_staff()
    num_whole_staff = count_whole_staff()

    for e in employees:
        manager = e.is_manager()
        employee_type = get_employee_type_display(e.employee_type)
        department = get_department_display(e.department)
        try:
            recently = get_working_hour_tobe_assign(e)  # 直近から適用される勤務時間
            try:
                oh = get_employee_hour(e, datetime.date.today())
                working_hour = str(oh)
            except NoAssignedWorkingHourError:
                working_hour = "%s (%s～)" % (recently.working_hours, recently.date)
        except ValueError:
            working_hour = "未設定"

        employee_status = get_employee_status_display(e, datetime.date.today())

        employee_data = {
            "department": department,
            "employee_type": employee_type,
            "basic_info": e,
            "working_hour": working_hour,
            "manager": manager,
            "include_overtime_pay": e.include_overtime_pay,
            "employee_no": e.employee_no,
            "is_active": e.user.is_active,
            "status": employee_status,
        }
        if hide_deactive_staff and not e.user.is_active:
            pass
        elif request.user.is_staff or request.user.permission.enable_add_staff:
            employee_list.append(employee_data)
        elif (
            request.user.permission.enable_view_temporary_staff_record
            and e.employee_type == models.Employee.TYPE_TEMPORARY_STAFF
        ):
            employee_list.append(employee_data)
        elif (
            request.user.permission.enable_view_outsource_staff_record
            and e.employee_type == models.Employee.TYPE_OUTSOURCING_STAFF
        ):
            employee_list.append(employee_data)

    params = {"employees": employee_list}
    params["checked"] = "checked" if hide_deactive_staff else ""

    params["whole_staff"] = num_whole_staff
    params["current_staff"] = num_active_staff

    return render(request, "sao/employee_list.html", params)


@login_required
def modify_record(request, record_id, year, month):
    """
    記録修正
    """
    msg = ""
    if request.method == "POST":
        record = get_object_or_404(models.EmployeeDailyRecord, id=record_id)
        form = forms.ModifyRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            logger.info(f"{request.user}が変更した: {record} {record.status}")
            return redirect("sao:employee_record")
    else:
        record = get_object_or_404(models.EmployeeDailyRecord, id=record_id)
        form = forms.ModifyRecordForm(instance=record)

    # 外出時間を取得する
    day_start = (
        record.clock_in
        if record.clock_in
        else core.datetime.datetime.combine(record.date, datetime.time(hour=5))
    )
    day_end = (
        record.clock_out
        if record.clock_out
        else core.datetime.datetime.combine(record.date, datetime.time(hour=5))
        + datetime.timedelta(days=1)
    )
    steppingouts = models.SteppingOut.objects.filter(
        employee=record.employee, out_time__gte=day_start, return_time__lt=day_end
    )

    return render(
        request,
        "sao/modify_record.html",
        {
            "record": record,
            "form": form,
            "year": year,
            "month": month,
            "msg": msg,
            "steppingouts": steppingouts,
        },
    )


@login_required
def employee_record(request):
    """■勤務記録"""
    if request.method == "POST":
        form = forms.StaffYearMonthForm(request.POST)
        if form.is_valid() and int(request.POST["employee"]) != 0:
            # '計算ボタン'を押されてここ通る
            employee = models.Employee.objects.get(id=request.POST["employee"])

            from_date = datetime.datetime.strptime(
                form.cleaned_data["yearmonth"], "%Y-%m"
            ).date()
            to_date = get_next_month_date(from_date)

            last_sunday = get_last_sunday(from_date)
            next_sunday = get_next_sunday(to_date)

            # 前月の最終日曜日から次月の最初の日曜日までのデータを集める
            attendances = get_attendance_in_period(employee, last_sunday, next_sunday)
            if len(attendances) <= 0:
                pass
            else:
                printable_calculated = attendances

                # 集計
                summed_up = attendance.sumup_attendances(calculated)
                printable_summed_up = summed_up

                # まるめ
                rounded = core.round_attendance_summary(summed_up)
                printable_rounded = rounded

                week_work_time = core.accumulate_weekly_working_hours(records)

                return render(
                    request,
                    "sao/view.html",
                    {
                        "form": form,
                        "duty_result": printable_calculated,
                        "total_result": printable_summed_up,
                        "rounded_result": printable_rounded,
                        "employee": employee,
                        "year": from_date.year,
                        "month": from_date.month,
                        "week_work_time": week_work_time,
                        "today": datetime.date.today(),
                    },
                )
    elif "employee" in request.GET:
        # 修正から戻ってきたときにここ通る
        employee = models.Employee.objects.get(id=request.GET["employee"])

        from_date = datetime.date(
            int(request.GET["year"]), int(request.GET["month"]), 1
        )
        to_date = get_next_month_date(from_date)

        form = forms.StaffYearMonthForm()

        # 前月の最終日曜日から次月の最初の日曜日までのデータを集める
        attendances = get_attendance_in_period(
            employee, get_last_sunday(from_date), get_next_sunday(to_date)
        )
        start = datetime.datetime.combine(
            get_last_sunday(from_date), datetime.time(0, 0)
        )
        end = datetime.datetime.combine(
            get_next_sunday(to_date), datetime.time(0, 0)
        ) + datetime.timedelta(days=1)
        period = Period(start, end)
        attendances = fill_missiing_attendance(employee, period, attendances)
        attendances[-1].total_over = tally_over_work_time(from_date.month, attendances)

        printable_calculated = attendances

        summed_up = tally_attendances(attendances)
        printable_summed_up = summed_up

        rounded = core.round_attendance_summary(summed_up)
        printable_rounded = rounded

        week_work_time = core.accumulate_weekly_working_hours(attendances)

        return render(
            request,
            "sao/view.html",
            {
                "form": form,
                "duty_result": printable_calculated,  # 勤務結果
                "total_result": printable_summed_up,  # 合算結果
                "rounded_result": printable_rounded,  # まるめ結果
                "employee": employee,
                "year": from_date.year,
                "month": from_date.month,
                "week_work_time": week_work_time,
                "today": datetime.date.today(),
            },
        )

    else:
        form = forms.StaffYearMonthForm()
    return render(request, "sao/view.html", {"form": form})


@login_required
def edit_employee(request, employee_no):
    """社員情報の編集"""
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    if request.method == "POST":
        form = forms.EditEmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            is_manager = form.cleaned_data["manager"]
            employee = form.save()

            # 管理職情報を更新する
            if is_manager:
                if not employee.is_manager():
                    models.Manager(manager=employee).save()
            else:
                if employee.is_manager():
                    manager = get_object_or_404(
                        models.Manager.objects, manager=employee
                    )
                    manager.delete()

            logger.info("%s: %sの情報を変更しました" % (request.user, employee))
            return redirect("sao:employee_list")
    else:
        # get
        is_manager = employee.is_manager()
        form = forms.EditEmployeeForm(
            instance=employee, initial={"manager": is_manager}
        )
    return render(
        request,
        "sao/edit_employee.html",
        {"form": form, "employee": employee},
    )


@login_required
def add_employee(request):
    """社員情報の追加"""
    form = forms.AddEmployeeForm(request.POST or None)
    if request.method != "POST":
        return render(request, "sao/add_employee.html", {"form": form})

    if form.is_valid():
        # 姓名から空白文字を削除
        (sei, mei) = re.split("[\s　]", form.cleaned_data["name"])
        name = sei + mei

        employee_no = form.cleaned_data["employee_no"]

        # アカウント作成
        user = create_user(
            form.cleaned_data["accountname"],
            sei,
            mei,
            form.cleaned_data["accountname"],
            form.cleaned_data["email"],
        )

        # スタッフ作成
        employee = create_employee(
            employee_no=employee_no,
            name=name,
            join_date=form.cleaned_data["join_date"],
            leave_date=datetime.date(2099, 12, 31),
            payed_holiday=0,
            employee_type=form.cleaned_data["type"],
            department=form.cleaned_data["department"],
            user=user,
        )
        if "manager" in request.POST:
            manager = models.Manager(manager=employee)
            manager.save()
        logger.info(
            "%sが%sを%s付け入社の処理をした"
            % (request.user, employee, employee.join_date)
        )
        return redirect("sao:employee_list")

    return render(request, "sao/add_employee.html", {"form": form})


def leave_from_company(request, employee_no):
    """退社処理"""
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    form = forms.LeaveFromCompanyForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            leave_date = form.cleaned_data["leave_date"]
            # 退社日を設定する
            employee.leave_date = leave_date
            employee.save()
            # アカウントはアクティブのまま（リストには残したい）
            # user = employee.user
            # user.is_active = False
            # user.save()
            logger.info(
                "%sが%sを%sに退職するように処理した"
                % (request.user, employee, employee.leave_date)
            )
            messages.success(request, f"{employee}を{leave_date}付で退職にしました")
            return redirect("sao:employee_list")

    if employee.leave_date < datetime.date(2099, 12, 31):
        if employee.leave_date < datetime.date.today():
            messages.info(request, f"{employee}は{employee.leave_date}に退社しています")
        else:
            messages.info(request, f"{employee}は{employee.leave_date}に退社予定です")
    return render(
        request,
        "sao/leave_from_company.html",
        {
            "form": form,
            "employee": employee,
            "leaved": employee.leave_date < datetime.date(2099, 12, 31),
        },
    )


@login_required
def cancel_leave_from_company(request, employee_no):
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    employee.leave_date = datetime.date(2099, 12, 31)
    employee.save()
    messages.success(request, f"{employee}の退社予定をキャンセルしました")
    return redirect("sao:employee_list")


@login_required
def attendance_summary(request):
    """■勤務実績一覧"""
    if request.method == "GET":
        form = forms.YearMonthForm(request.GET)
        if form.is_valid():
            from_date = datetime.datetime.strptime(
                form.cleaned_data["yearmonth"], "%Y-%m"
            ).date()
        else:
            form = forms.YearMonthForm()
            from_date = get_first_day(datetime.date.today())

        to_date = get_next_month_date(from_date)

        start = datetime.datetime.combine(from_date, datetime.time(0, 0))
        end = datetime.datetime.combine(
            to_date, datetime.time(0, 0)
        ) + datetime.timedelta(days=1)
        period = Period(start, end)

        hide_deactive_staff = False
        if "f_deactive" in request.GET:
            hide_deactive_staff = True
        elif "hide_deactive_staff" in request.COOKIES:
            hide_deactive_staff = True

        summaries = []
        employees = models.Employee.objects.all().order_by("employee_no")
        if hide_deactive_staff:
            employees = employees.filter(user__is_active=True)
        else:
            employees = employees.order_by("-user__is_active", "employee_no")

        for employee in employees:
            attendances = get_attendance_in_period(employee, from_date, to_date)
            if len(attendances) <= 0:
                continue
            attendances = fill_missiing_attendance(employee, period, attendances)
            total_overwork = tally_over_work_time(from_date.month, attendances)
            daycount = core.count_days(attendances, from_date)
            summed_up = tally_attendances(attendances)

            summary = {
                "type": get_employee_type_display(employee.employee_type),
                "department": get_department_display(employee.department),
                "employee": employee,
                "daycount": daycount,
                "overtime_work": summed_up["out_of_time"],
            }
            summaries.append(summary)
        params = {
            "form": form,
            "summaries": summaries,
            "year": from_date.year,
            "month": from_date.month,
        }
        params["checked"] = "checked" if hide_deactive_staff else ""
        response = render(request, "sao/attendance_summary.html", params)
        response.set_cookie("hide_deactive_staff", hide_deactive_staff)
        return response
    else:
        # 年月指定
        form = forms.YearMonthForm()
    return render(request, "sao/attendance_summary.html", {"form": form})


def time_clock(request):
    """■打刻"""
    employee = models.Employee.objects.get(user=request.user)
    stamp = datetime.datetime.now().replace(microsecond=0)
    if request.method == "POST":
        models.WebTimeStamp(employee=employee, stamp=stamp).save()

    day_switch_time = get_day_switch_time()
    business_day = normalize_to_business_day(stamp)
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee,
        stamp__gte=datetime.datetime.combine(business_day.date(), day_switch_time),
    ).order_by("-stamp")
    return render(
        request, "sao/time_clock.html", {"employee": employee, "stamps": stamps}
    )


@login_required
def permission(request):
    """権限設定"""
    staffs = models.Employee.objects.filter(user__is_active=True)
    staffs = staffs.order_by("employee_no")
    return render(request, "sao/permission.html", {"staffs": staffs})


@login_required
def modify_permission(request, user_id):
    """権限変更"""
    user = User.objects.get(id=user_id)
    if request.method == "POST":
        form = forms.ModifyPermissionForm(request.POST)
        if form.is_valid():
            user.is_staff = form.cleaned_data["is_staff"]
            user.permission.enable_view_detail = form.cleaned_data["enable_view_detail"]
            user.permission.enable_stamp_on_web = form.cleaned_data[
                "enable_stamp_on_web"
            ]
            user.permission.enable_add_staff = form.cleaned_data["enable_add_staff"]
            user.permission.save()
            user.save()
            logger.info("%sが%sの権限を変更しました" % (request.user, user))
        return redirect("sao:permission")
    else:
        form = forms.ModifyPermissionForm(
            {
                "is_staff": user.is_staff,
                "enable_view_detail": user.permission.enable_view_detail,
                "enable_stamp_on_web": user.permission.enable_stamp_on_web,
                "enable_add_staff": user.permission.enable_add_staff,
            }
        )

    return render(request, "sao/modify_permission.html", {"form": form, "user": user})


@login_required
def holiday_settings(request):
    """公休日設定"""
    form = forms.RegisterHolidayForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            holiday = form.save()
            logger.info("%sが公休日(%s)を登録しました" % (request.user, holiday))

    holidays = models.Holiday.objects.all().order_by("date")
    return render(
        request, "sao/holiday_settings.html", {"form": form, "holidays": holidays}
    )


@login_required
def delete_holiday(request, id):
    """公休日設定削除"""
    holiday = get_object_or_404(models.Holiday, id=id)
    holiday.delete()
    logger.info("%sが公休日(%s)を削除しました" % (request.user, holiday))
    messages.success(request, f"{holiday}を削除しました")
    return redirect("sao:holiday_settings")


def progress(request, pk):
    """現在の進捗ページ"""
    context = {"progress": get_object_or_404(models.Progress, pk=pk)}
    return render(request, "sao/progress.html", context)


def update_annual_leave(request):
    """年次休暇の更新"""
    today = datetime.date.today()
    for employee in models.Employee.objects.all():
        employee.payed_holiday = 0.0
        employee.save()

    for employee in models.Employee.objects.filter(
        employee_type=models.Employee.TYPE_PERMANENT_STAFF
    ).filter(user__is_active=True):
        employee.payed_holiday = core.get_annual_paied_holiday_days(
            today, employee.join_date
        )

        d = core.get_recent_day_of_annual_leave_update(
            datetime.date.today(), employee.join_date
        )

        records = (
            models.EmployeeDailyRecord.objects.filter(employee=employee)
            .filter(date__gte=d)
            .order_by("date")
        )
        for record in records:
            if record.status == WorkingStatus.C_YUUKYUU:
                employee.payed_holiday -= 1.0
            if record.status in [
                WorkingStatus.C_YUUKYUU_GOZENKYU,
                WorkingStatus.C_YUUKYUU_GOGOKYUU_NASHI,
                WorkingStatus.C_YUUKYUU_GOGOKYUU_ARI,
            ]:
                employee.payed_holiday -= 0.5

        employee.save()

    return redirect("sao:employee_list")


@login_required
def download_csv(request, employee_no, year, month):
    """csvダウンロード"""

    def make_filename(employee, year, month):
        return employee.user.username + "-" + str(year) + "-" + str(month)

    csv_date = datetime.date(year=year, month=month, day=1)
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    filename = make_filename(employee, year, month)
    response = HttpResponse(content_type="text/csv; charset=Shift-JIS")
    response["Content-Disposition"] = 'attachment; filename="' + filename + '.csv"'
    records = core.collect_timerecord_by_month(employee, csv_date)
    try:
        calculated = attendance.tally_monthly_attendance(csv_date.month, records)
    except NoAssignedWorkingHourError:
        sumup = attendance.sumup_attendances([])
        rounded = core.round_attendance_summary(sumup)
        messages.warning(
            request, f"・{employee}の打刻データが存在しないためCVSの出力ができません"
        )
        return render(
            request,
            "sao/attendance_detail.html",
            {
                "employee": employee,
                "year": datetime.date.today().year,
                "month": datetime.date.today().month,
                "total_result": sumup,
                "rounded_result": rounded,
                "today": datetime.date.today(),
                "mypage": True,
            },
        )

    # 集計する
    summed_up = attendance.sumup_attendances(calculated)

    # 時間外勤務についての警告
    # warn_class, warn_title = utils.warning_to_out_of_time(summed_up["out_of_time"])

    # 計算結果をまるめる
    rounded = core.round_attendance_summary(summed_up)

    ## HttpResponseオブジェクトはファイルっぽいオブジェクトなので、csv.writerにそのまま渡せます。
    writer = csv.writer(response)

    writer.writerow(
        [
            "日",
            "区分",
            "出社時刻",
            "退社時刻",
            "実働時間",
            "遅刻",
            "早退",
            "時間外",
            "深夜",
            "法定休日",
            "所定休日",
        ]
    )
    for r in calculated:
        writer.writerow(
            [
                r.date,
                r.flag,
                r.clock_in,
                r.clock_out,
                r.work,
                r.late,
                r.before,
                r.out_of_time,
                r.night,
                r.legal_holiday,
                r.holiday,
            ]
        )
    # print(summed_up["out_of_time"])
    writer.writerow(
        [
            "",
            "",
            "",
            "",
            format_seconds_to_hhmmss(summed_up["work"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["late"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["before"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["out_of_time"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["night"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["legal_holiday"].total_seconds()),
            format_seconds_to_hhmmss(summed_up["holiday"].total_seconds()),
        ]
    )

    writer.writerow(
        [
            "",
            "",
            "",
            "",
            format_seconds_to_hhmmss(rounded["work"].total_seconds()),
            format_seconds_to_hhmmss(rounded["late"].total_seconds()),
            format_seconds_to_hhmmss(rounded["before"].total_seconds()),
            format_seconds_to_hhmmss(rounded["out_of_time"].total_seconds()),
            format_seconds_to_hhmmss(rounded["night"].total_seconds()),
            format_seconds_to_hhmmss(rounded["legal_holiday"].total_seconds()),
            format_seconds_to_hhmmss(rounded["holiday"].total_seconds()),
        ]
    )
    return response


@login_required
def web_timestamp_view(request, employee_no):
    """WEB打刻の閲覧"""
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    stamps = models.WebTimeStamp.objects.filter(employee=employee).order_by("-stamp")
    return render(
        request, "sao/web_timestamp_view.html", {"employee": employee, "stamps": stamps}
    )


@login_required
def add_steppingout(request, record, year, month):
    """外出時間の追加"""
    record = get_object_or_404(models.EmployeeDailyRecord, id=record)
    employee = record.employee
    msg = ""

    day_start = (
        record.clock_in
        if record.clock_in
        else datetime.datetime.combine(record.date, datetime.time(hour=5))
    )
    day_end = (
        record.clock_out
        if record.clock_out
        else datetime.datetime.combine(record.date, datetime.time(hour=5))
        + datetime.timedelta(days=1)
    )
    steppingouts = models.SteppingOut.objects.filter(
        employee=employee, out_time__gte=day_start, return_time__lt=day_end
    )

    if request.method == "POST":
        form = forms.AddSteppingOutForm(request.POST)
        if form.is_valid():
            out_time = datetime.datetime.combine(
                record.date, form.cleaned_data["out_time"]
            )
            return_time = datetime.datetime.combine(
                record.date, form.cleaned_data["return_time"]
            )
            steppingout = models.SteppingOut.objects.filter(
                out_time=out_time, return_time=return_time
            )
            if steppingout:
                # 登録済み
                msg = "二重登録"
            else:
                # 区間の重複
                def is_overlapped(t, steppingouts):
                    for steppingout in steppingouts:
                        if t >= steppingout.out_time and t <= steppingout.return_time:
                            return True
                    return False

                if not is_overlapped(out_time, steppingouts) and not is_overlapped(
                    return_time, steppingouts
                ):
                    models.SteppingOut(
                        employee=employee, out_time=out_time, return_time=return_time
                    ).save()
                    return redirect(
                        "sao:modify_record", record=record.id, year=year, month=month
                    )
                    # form = forms.AddSteppingOutForm()
                    # steppingouts = models.SteppingOut.objects.filter(employee=employee, out_time__gte=day_start, return_time__lt=day_end)
                else:
                    msg = "時間が重複しています"
        else:
            msg = "フォームが無効です"
    else:
        form = forms.AddSteppingOutForm()

    webstamps = [
        x.stamp
        for x in models.WebTimeStamp.objects.filter(
            employee=employee, stamp__date=record.date
        ).order_by("-stamp")
    ]

    return render(
        request,
        "sao/add_steppingout.html",
        {
            "record": record.id,
            "year": year,
            "month": month,
            "employee": employee,
            "form": form,
            "steppingouts": steppingouts,
            "webstamps": webstamps,
            "msg": msg,
        },
    )


@login_required
def modify_steppingout(request, steppingout, record, year, month):
    """外出時間の修正"""
    steppingout = get_object_or_404(models.SteppingOut, id=steppingout)
    record = get_object_or_404(models.EmployeeDailyRecord, id=record)
    if request.method == "POST":
        form = forms.AddSteppingOutForm(request.POST)
        if form.is_valid():
            steppingout.out_time = datetime.datetime.combine(
                record.date, form.cleaned_data["out_time"]
            )
            steppingout.return_time = datetime.datetime.combine(
                record.date, form.cleaned_data["return_time"]
            )
            steppingout.save()
            return redirect(
                "sao:add_steppingout", record=record.id, year=year, month=month
            )
    else:
        initial = {
            "out_time": steppingout.out_time.time,
            "return_time": steppingout.return_time.time,
        }
        form = forms.AddSteppingOutForm(initial=initial)
    return render(
        request,
        "sao/modify_steppingout.html",
        {
            "steppingout": steppingout.id,
            "record": record,
            "year": year,
            "month": month,
            "form": form,
        },
    )


@login_required
def del_steppingout(request, steppingout, record, year, month):
    """外出時間の削除"""
    models.SteppingOut.objects.get(id=steppingout).delete()
    return redirect("sao:add_steppingout", record=record, year=year, month=month)


@login_required
def change_stamp_id(request):
    """打刻IDの変更"""
    employee = models.Employee.objects.get(employee_no=57)
    records = models.WebTimeStamp.objects.filter(employee=employee)

    return HttpResponse("records = %d" % records.count())


def get_employee_json(request):
    """社員情報のJSON取得"""
    employees = models.Employee.objects.all()
    ary = []
    for employee in employees:
        ary.append({"employee_no": employee.employee_no})

    return HttpResponse(
        json.dumps(ary, ensure_ascii=False, indent=2), content_type="application/json"
    )


def fix_holiday(request):
    """休日の修正"""
    employees = models.Employee.objects.filter(user__is_active=True)
    for e in employees:
        rec = models.EmployeeDailyRecord.objects.filter(employee=e)
        rec = rec.filter(date__gte="2021-12-28")
        rec = rec.filter(date__lt="2022-01-05")
        for r in rec:
            r.flag = "休日"
            r.save()

    return HttpResponse("done")


@login_required
def working_hours_view(request):
    return render(
        request,
        "sao/working_hours_list.html",
        {
            "working_hours": list(models.WorkingHour.objects.filter(is_active=True)),
        },
    )


@login_required
def add_working_hours(request):
    if request.method == "POST":
        form = forms.WorkingHourForm(request.POST)
        if form.is_valid():
            working_hour = form.save()
            messages.success(
                request, f"勤務時間「{working_hour.category}」を追加しました。"
            )
            return redirect("sao:working_hours_view")
    else:
        form = forms.WorkingHourForm()
    return redirect("sao:working_hours_view")


@login_required
def del_working_hours(request, id):
    working_hour = get_object_or_404(models.WorkingHour, id=id)
    working_hour.is_active = False
    working_hour.save()
    messages.success(request, f"勤務時間「{working_hour.category}」を削除しました。")
    return redirect("sao:working_hours_view")


@login_required
def update_working_hours(request, id):
    logger.info("update working hours")
    workinghour = get_object_or_404(models.WorkingHour, id=id)

    if request.method == "POST":
        form = forms.WorkingHourForm(request.POST, instance=workinghour)
        if form.is_valid():
            working_hour = form.save()
            messages.success(
                request, f"勤務時間「{working_hour.category}」を更新しました。"
            )
        else:
            # バリデーションエラー時
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    return redirect("sao:working_hours_view")


@login_required
def day_switch_time_view(request):

    # DaySwitchTimeは1件しか存在しないので、なければ作成する
    if not models.DaySwitchTime.objects.exists():
        models.DaySwitchTime.objects.create(switch_time=datetime.time(hour=5, minute=0))

    return render(
        request,
        "sao/day_switch_time_view.html",
        {
            "day_switch_time": models.DaySwitchTime.objects.all()[0],
        },
    )


def day_switch_time_edit(request, id):

    day_switch_time = get_object_or_404(models.DaySwitchTime, id=id)
    form = forms.DaySwitchTimeForm(request.POST or None, instance=day_switch_time)
    if request.method == "POST":
        if form.is_valid():
            day_switch_time = form.save()
            messages.success(
                request,
                f"日付切り替え時間を「{day_switch_time.switch_time}」に変更しました。",
            )
            logger.info(
                f"日付切り替え時間を「{day_switch_time.switch_time}」に変更しました。"
            )
            return redirect("sao:day_switch_time_view")

    return render(
        request,
        "sao/day_switch_time_edit.html",
        {
            "form": form,
        },
    )


@csrf_exempt
def day_switch(request):
    """日時切り替え処理
    POSTで渡されたdateの前日の打刻を処理する
    """

    if request.method == "POST":
        date = request.POST.get("date")
        if not date:
            return HttpResponse("no date")
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    else:
        date = datetime.date.today() - datetime.timedelta(days=1)  # 昨日

    logger.info(f"{date} の切り替え作業を開始します")

    # WebTimeStampを集めてEmployeeDailyRecordを生成する
    employees = (
        models.Employee.objects.filter(user__is_active=True)
        .filter(join_date__lte=date)
        .filter(leave_date__gte=date)
    )
    for employee in employees:
        logger.info(f"処理中: {employee} {date}")

        # 打刻から勤怠記録を生成する
        finalize_daily_record(employee, date)

    logger.info(f"{date} の切り替え作業が完了しました")
    return HttpResponse("day switch done for " + str(date))


@login_required
def setup_sample_data(request):
    """サンプルデータのセットアップ"""
    utils_setup_sample_data()
    return HttpResponse("sample data setup done")
