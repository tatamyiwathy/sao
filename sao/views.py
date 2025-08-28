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
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import CreateView
from . import calendar, core, forms, models, utils
from .core import (
    get_employee_hour,
    get_working_hours_tobe_assign,
    NoSpecifiedWorkingHoursError,
)
from .const import Const
from .attendance import Attendance
from .working_status import WorkingStatus

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

        if (today - attn.date).days < 2:
            # 猶予期間
            return {}

        if utils.is_missed_stamp(attn.clock_in, attn.clock_out):
            # 打刻が片方だけ
            warnings["missed_stamp"] = True
        if not calendar.is_holiday(attn.date) and utils.is_empty_stamp(
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
        if attn.before > Const.TD_ZERO:
            # 早退
            warnings["leave_early"] = True
        if attn.night > Const.TD_ZERO:
            # 深夜
            warnings["midnight_work"] = True

        if attn.steppingout > Const.TD_ZERO:
            # 外出
            warnings["steppingout"] = True

        return warnings

    def is_need_overwork_notification(attn: Attendance, today: datetime.date) -> bool:
        """残業の通知が必要かどうかを判定する"""
        if attn.summed_out_of_time <= datetime.timedelta(hours=25):
            return False

        if attn.remark:
            # 処理済み
            return False

        if (today - attn.date).days < 2:
            # 猶予期間
            return False

        if calendar.is_holiday(attn.date) and utils.is_empty_stamp(
            attn.clock_in, attn.clock_out
        ):
            return False

        return True

    def set_warning_message(
        attendances: list, view_date: datetime.date, today: datetime.date
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
            and (attendances[-1].summed_out_of_time <= datetime.timedelta(hours=25))
            and (attendances[-1].summed_out_of_time > datetime.timedelta(hours=23))
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
        # 集計
        records = core.collect_timerecord_by_month(employee, view_date)
        try:
            attendances = core.tally_monthly_attendance(view_date.month, records)
        except NoSpecifiedWorkingHoursError:
            return render(
                request, "sao/worker_detail_empty.html", {"empolyee": employee}
            )

        # messageで警告を表示する
        if employee.employee_type == models.Employee.TYPE_PERMANENT_STAFF:
            attendances = set_warning_message(attendances, view_date, today)

        # 集計する
        summed_up = core.sumup_attendances(attendances)

        # 時間外勤務についての警告
        warn_class, warn_title = utils.attention_overtime(summed_up["out_of_time"])

        # 計算結果をまるめる
        rounded = core.round_result(summed_up)

        daycount = core.count_days(attendances, view_date)

        return render(
            request,
            "sao/worker_detail.html",
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
            "sao/worker_detail_empty.html",
            {"message": "スーパーユーザーでログイン中"},
        )

    # 設定された勤務時間を取得する
    try:
        office_hours = get_employee_hour(employee, datetime.date.today())
    except ValueError:
        # 合流前で勤務時間が取得できない
        try:
            office_hours = get_working_hours_tobe_assign(employee)
        except ValueError:
            raise Http404("勤務時間設定がない")

    # 今日の出退勤時刻を取得する
    today = datetime.date.today()
    if datetime.datetime.now().hour < 5:
        # 日を跨いでる
        today = (datetime.datetime.now() - datetime.timedelta(days=1)).date()

    (fromTime, toTime) = utils.get_today_stamp(employee, today)

    if request.method == "POST":
        form = forms.YearMonthForm(request.POST)
        if form.is_valid():
            # employee = get_object_or_404(models.Employee, id=request.POST['employee'])
            date_on_view = datetime.datetime.strptime(
                form.cleaned_data["yearmonth"], "%Y-%m"
            ).date()
            return make_view(employee, date_on_view, today)
        logger.warning("form is invalid %s" % request.POST)
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
    from_date = datetime.date(year=year, month=month, day=1)
    to_date = calendar.get_next_month_date(from_date)
    office_hours = get_employee_hour(employee, datetime.date.today())

    query = (
        models.TimeRecord.objects.filter(employee=employee)
        .filter(date__gte=from_date)
        .filter(date__lt=to_date)
        .order_by("date")
    )

    try:
        calculated = core.tally_monthly_attendance(from_date.month, query)
    except NoSpecifiedWorkingHoursError:
        return render(
            request,
            "sao/worker_detail_empty.html",
            {
                "message": f"{employee}の勤務時間が設定されていないため勤怠が表示できません"
            },
        )

    summed_up = core.sumup_attendances(calculated)
    rounded_result = core.round_result(summed_up)

    daycount = core.count_days(calculated, from_date)

    return render(
        request,
        "sao/worker_detail.html",
        {
            "duty_result": calculated,
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
    errors = None
    employee = get_object_or_404(models.Employee, employee_no=employee_no)
    if request.method == "POST":
        employee_hour = models.EmployeeHour(employee=employee)
        form = forms.ApplyWorkingHoursForm(request.POST, instance=employee_hour)
        if form.is_valid():
            date = form.cleaned_data["date"]
            working_hours = form.cleaned_data["working_hours"]
            q = (
                models.EmployeeHour.objects.filter(employee=employee)
                .filter(date=date)
                .filter(working_hours=working_hours)
            )
            if len(q) == 0:
                form.save()
                logger.info("%sが%sを追加した" % (request.user, employee_hour))
                return redirect("sao:employee_list")
            else:
                errors = "すでに設定されています"

    else:
        form = forms.ApplyWorkingHoursForm(
            instance=employee, initial={"date": datetime.date.today()}
        )
    employee_hours = models.EmployeeHour.objects.filter(
        employee=employee
    ).order_by("-date")
    return render(
        request,
        "sao/office_hours_list.html",
        {
            "employee": employee,
            "office_hours": employee_hours,
            "form": form,
            "errors": errors,
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
        employee_type = utils.get_employee_type(e.employee_type)
        department = utils.get_department(e.department)
        try:
            recently = get_working_hours_tobe_assign(e)  # 直近から適用される勤務時間
            try:
                oh = get_employee_hour(e, datetime.date.today())
                working_hour = str(oh)
            except ValueError:
                working_hour = "* %s" % recently
        except ValueError:
            working_hour = "未設定"

        employee_status = utils.get_employee_status(e, datetime.date.today())

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
        record = get_object_or_404(models.TimeRecord, id=record_id)
        form = forms.ModifyRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            logger.info(f"{request.user}が変更した: {record} {record.status}")
            return redirect("sao:employee_record")
    else:
        record = get_object_or_404(models.TimeRecord, id=record_id)
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
            to_date = calendar.get_next_month_date(from_date)

            last_sunday = calendar.get_last_sunday(from_date)
            next_sunday = calendar.get_next_sunday(to_date)

            # 前月の最終日曜日から次月の最初の日曜日までのデータを集める
            records = (
                models.TimeRecord.objects.filter(employee=employee)
                .filter(date__gte=last_sunday)
                .filter(date__lt=next_sunday)
                .order_by("date")
            )
            if len(records) <= 0:
                pass
            else:
                try:
                    calculated = core.tally_monthly_attendance(from_date.month, records)
                except NoSpecifiedWorkingHoursError:
                    return render(
                        request,
                        "sao/worker_detail_empty.html",
                        {
                            "message": f"{employee}の勤務時間が設定されていないため勤怠が表示できません"
                        },
                    )

                printable_calculated = calculated

                # 集計
                summed_up = core.sumup_attendances(calculated)
                printable_summed_up = summed_up

                # まるめ
                rounded = core.round_result(summed_up)
                printable_rounded = rounded

                week_work_time = core.accumulate_weekly_working_hours(records)

                # for r in calculated:
                #     print(r.record_id)

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
        to_date = calendar.get_next_month_date(from_date)

        form = forms.StaffYearMonthForm()

        # 前月の最終日曜日から次月の最初の日曜日までのデータを集める
        records = (
            employee.timerecord_set.filter(employee=employee)
            .filter(date__gte=calendar.get_last_sunday(from_date))
            .filter(date__lt=calendar.get_next_sunday(to_date))
            .order_by("date")
        )

        try:
            calculated = core.tally_monthly_attendance(from_date.month, records)
        except NoSpecifiedWorkingHoursError:
            return render(
                request,
                "sao/worker_detail_empty.html",
                {
                    "message": f"{employee}の勤務時間が設定されていないため勤怠が表示できません"
                },
            )

        printable_calculated = calculated

        summed_up = core.sumup_attendances(calculated)
        printable_summed_up = summed_up

        rounded = core.round_result(summed_up)
        printable_rounded = rounded

        week_work_time = core.accumulate_weekly_working_hours(records)

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
        print("nande")
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
        user = utils.create_user(form.cleaned_data["accountname"], sei, mei, form.cleaned_data["accountname"], form.cleaned_data['email'])

        # スタッフ作成
        employee = utils.create_employee(
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
    form = forms.LeaveFromCompanyForm(request.POST or None)
    if form.is_valid():
        employee = get_object_or_404(models.Employee, employee_no=employee_no)
        # 退社日を設定する
        employee.leave_date = request.POST["leave_date"]
        employee.save()
        # アカウントはアクティブのまま（リストには残したい）
        # user = employee.user
        # user.is_active = False
        # user.save()
        logger.info(
            "%sが%sを%sに退職するように処理した"
            % (request.user, employee, employee.leave_date)
        )
        return redirect("sao:employee_list")
    
    form = forms.LeaveFromCompanyForm()
    return render(request, "sao/leave.html", {"form": form, "employee": employee})


@login_required
def overview(request):
    """■勤務実績一覧"""
    if request.method == "GET":
        form = forms.YearMonthForm(request.GET)
        if form.is_valid():
            from_date = datetime.datetime.strptime(
                form.cleaned_data["yearmonth"], "%Y-%m"
            ).date()
        else:
            form = forms.YearMonthForm()
            from_date = calendar.get_first_day(datetime.date.today())

        to_date = calendar.get_next_month_date(from_date)

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

        stamps = models.TimeRecord.objects.filter(date__gte=from_date).filter(
            date__lt=to_date
        )
        for employee in employees:
            records = stamps.filter(employee=employee).order_by("date")

            try:
                calculated = core.tally_monthly_attendance(from_date.month, records)
            except NoSpecifiedWorkingHoursError:
                return render(
                    request,
                    "sao/worker_detail_empty.html",
                    {
                        "message": f"{employee}の勤務時間が設定されていないため勤怠が表示できません"
                    },
                )

            daycount = core.count_days(calculated, from_date)

            summed_up = core.sumup_attendances(calculated)

            summary = {
                "type": utils.get_employee_type(employee.employee_type),
                "department": utils.get_department(employee.department),
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
        response = render(request, "sao/overview.html", params)
        response.set_cookie("hide_deactive_staff", hide_deactive_staff)
        return response
    else:
        # 年月指定
        form = forms.YearMonthForm()
    return render(request, "sao/overview.html", {"form": form})


def time_clock(request):
    """■打刻"""
    employee = models.Employee.objects.get(user=request.user)
    stamp = datetime.datetime(*datetime.datetime.now().timetuple()[:6])
    if request.method == "POST":
        models.WebTimeStamp(employee=employee, stamp=stamp).save()

    start = datetime.datetime(stamp.year, stamp.month, stamp.day, 5, 0, 0)
    if stamp.hour < 5:
        # 日を跨いでる
        start = stamp - datetime.timedelta(days=1)
        start = datetime.datetime(start.year, start.month, start.day, 5, 0, 0)
    stamps = models.WebTimeStamp.objects.filter(
        employee=employee, stamp__gte=start
    ).order_by("-stamp")
    return render(
        request, "sao/time_clock.html", {"employee": employee, "stamps": stamps}
    )


@login_required
def password(request):
    """パスワード変更"""
    message = None
    success = False
    form = forms.ChangePasswordForm(request.POST)
    if form.is_valid():
        password = request.POST["password"]
        confirm = request.POST["confirm"]
        if password == confirm:
            user = request.user
            user.set_password(password)
            user.save()
            success = True
            return redirect("sao:home")
        else:
            message = "入力されたパスワードと確認の文字列が一致しません"

    return render(
        request,
        "sao/change_password.html",
        {"form": form, "message": message, "success": success},
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
            user.permission.enable_view_temporary_staff_record = form.cleaned_data[
                "enable_view_temporary_staff_record"
            ]
            user.permission.enable_view_outsource_staff_record = form.cleaned_data[
                "enable_view_outsource_staff_record"
            ]
            user.permission.enable_view_dev_staff_record = form.cleaned_data[
                "enable_view_dev_staff_record"
            ]
            user.permission.enable_view_detail = form.cleaned_data["enable_view_detail"]
            user.permission.enable_stamp_on_web = form.cleaned_data[
                "enable_stamp_on_web"
            ]
            user.permission.enable_regist_event = form.cleaned_data[
                "enable_regist_event"
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
                "enable_view_temporary_staff_record": user.permission.enable_view_temporary_staff_record,
                "enable_view_outsource_staff_record": user.permission.enable_view_outsource_staff_record,
                "enable_view_dev_staff_record": user.permission.enable_view_dev_staff_record,
                "enable_view_detail": user.permission.enable_view_detail,
                "enable_stamp_on_web": user.permission.enable_stamp_on_web,
                "enable_regist_event": user.permission.enable_regist_event,
                "enable_add_staff": user.permission.enable_add_staff,
            }
        )

    return render(request, "sao/modify_permission.html", {"form": form, "user": user})


@login_required
def holiday_settings(request):
    """公休日設定"""
    if request.method == "POST":
        form = forms.RegisterHolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save()
            logger.info("%sが公休日(%s)を登録しました" % (request.user, holiday))
    else:
        if "del" in request.GET:
            id = request.GET["del"]
            target = models.Holiday.objects.filter(id=id)
            if target.count() > 0:
                holiday = models.Holiday.objects.get(id=id)
                target.delete()
                logger.info("%sが公休日(%s)を削除しました" % (request.user, holiday))
        form = forms.RegisterHolidayForm()
    holidays = models.Holiday.objects.all().order_by("date")
    return render(
        request, "sao/holiday_settings.html", {"form": form, "holidays": holidays}
    )


def req_test(request):
    return HttpResponse(r"POST") if request.method == "POST" else HttpResponse(r"GET")


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
            models.TimeRecord.objects.filter(employee=employee)
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

    def set_if_noexist(ary, key, val_else):
        if not key in ary:
            ary[key] = val_else

    def make_filename(employee, year, month):
        return employee.user.username + "-" + str(year) + "-" + str(month)

    csv_date = datetime.date(year=year, month=month, day=1)
    employee = get_object_or_404(models.Employee, employee_no=employee_no)

    filename = make_filename(employee, year, month)

    response = HttpResponse(content_type="text/csv; charset=Shift-JIS")
    response["Content-Disposition"] = 'attachment; filename="' + filename + '.csv"'

    records = core.collect_timerecord_by_month(employee.id, csv_date)
    if records is None:
        return Http404

    try:
        calculated = core.tally_monthly_attendance(csv_date.month, records)
    except NoSpecifiedWorkingHoursError:
        return render(
            request,
            "sao/worker_detail_empty.html",
            {
                "message": f"{employee}の勤務時間が設定されていないため勤怠が表示できません"
            },
        )

    # 集計する
    summed_up = core.sumup_attendances(calculated)

    # 時間外勤務についての警告
    # warn_class, warn_title = utils.warning_to_out_of_time(summed_up["out_of_time"])

    # 計算結果をまるめる
    rounded = core.round_result(summed_up)

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
    print(summed_up["out_of_time"])
    writer.writerow(
        [
            "",
            "",
            "",
            "",
            utils.print_total_sec(summed_up["work"].total_seconds()),
            utils.print_total_sec(summed_up["late"].total_seconds()),
            utils.print_total_sec(summed_up["before"].total_seconds()),
            utils.print_total_sec(summed_up["out_of_time"].total_seconds()),
            utils.print_total_sec(summed_up["night"].total_seconds()),
            utils.print_total_sec(summed_up["legal_holiday"].total_seconds()),
            utils.print_total_sec(summed_up["holiday"].total_seconds()),
        ]
    )

    writer.writerow(
        [
            "",
            "",
            "",
            "",
            utils.print_total_sec(rounded["work"].total_seconds()),
            utils.print_total_sec(rounded["late"].total_seconds()),
            utils.print_total_sec(rounded["before"].total_seconds()),
            utils.print_total_sec(rounded["out_of_time"].total_seconds()),
            utils.print_total_sec(rounded["night"].total_seconds()),
            utils.print_total_sec(rounded["legal_holiday"].total_seconds()),
            utils.print_total_sec(rounded["holiday"].total_seconds()),
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
    record = get_object_or_404(models.TimeRecord, id=record)
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
    record = get_object_or_404(models.TimeRecord, id=record)
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
        rec = models.TimeRecord.objects.filter(employee=e)
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
            'working_hours': list(models.WorkingHour.objects.filter(is_active=True)),
        },
    )

@login_required
def add_working_hours(request):
    if request.method == 'POST':
        form = forms.WorkingHourForm(request.POST)
        if form.is_valid():
            working_hour = form.save()
            messages.success(request, f'勤務時間「{working_hour.category}」を追加しました。')
            return redirect('sao:working_hours_view')
    else:
        form = forms.WorkingHourForm()
    return redirect('sao:working_hours_view')

@login_required
def del_working_hours(request, id):
    working_hour = get_object_or_404(models.WorkingHour, id=id)
    working_hour.is_active = False
    working_hour.save()
    messages.success(request, f'勤務時間「{working_hour.category}」を削除しました。')
    return redirect('sao:working_hours_view')

@login_required
def update_working_hours(request, id):
    logger.info("update working hours")    
    workinghour = get_object_or_404(models.WorkingHour, id=id)

    if request.method == "POST":
        form = forms.WorkingHourForm(request.POST, instance=workinghour)
        if form.is_valid():
            working_hour = form.save()
            messages.success(request, f'勤務時間「{working_hour.category}」を更新しました。')
        else:
            # バリデーションエラー時
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    return redirect('sao:working_hours_view')
