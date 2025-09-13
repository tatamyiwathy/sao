import re
import datetime
from django import forms
from django.core.exceptions import ObjectDoesNotExist
from sao.models import (
    Employee,
    EmployeeHour,
    Holiday,
    EmployeeDailyRecord,
    WorkingHour,
    DaySwitchTime,
)
from sao.working_status import WorkingStatus


class WorkingHourAssignForm(forms.ModelForm):
    """勤務時間を適用するフォーム"""

    class Meta:
        model = EmployeeHour
        fields = (
            "date",
            "working_hours",
        )
        widgets = {
            "working_hours": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(
                attrs={"type": "date", "class": "form-control datepicker-future"}
            ),
        }
        labels = {"working_hours": "勤務時間", "date": "適用開始日"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ここで初期値を設定する
        self.fields["working_hours"].queryset = WorkingHour.objects.filter(
            is_active=True
        )


class StaffYearMonthForm(forms.Form):
    """
    社員を選択・年月を入力 フォーム
    """

    employee = forms.ChoiceField(
        label="氏名", widget=forms.Select(attrs={"class": "form-select"})
    )
    yearmonth = forms.CharField(
        label="月",
        initial=datetime.date.today(),
        widget=forms.DateInput(
            attrs={"class": "MonthPicker form-control"}, format="%Y-%m"
        ),
    )

    def __init__(self, *args, **kwargs):
        super(forms.Form, self).__init__(*args, **kwargs)

        employees = Employee.objects.all().order_by("employee_no")
        targets = [(0, "------")]
        for eply in employees:
            if eply.user.is_active:
                name = eply.name
                if eply.employee_type == Employee.TYPE_PERMANENT_STAFF:
                    name = name
                elif eply.employee_type == Employee.TYPE_TEMPORARY_STAFF:
                    name = name + "(派)"
                else:
                    name = name + "(委)"

                targets.append((eply.pk, name))
        self.fields["employee"].choices = targets


class YearMonthForm(forms.Form):
    """
    年月フォーム
    """

    yearmonth = forms.DateField(
        label="",
        initial=datetime.date.today(),
        widget=forms.DateInput(
            attrs={
                "type": "month",
                "class": "form-control MonthPicker",
                "onBlur": "submit()",
            },
            format="%Y-%m",
        ),
    )


class ModifyRecordForm(forms.ModelForm):
    """勤怠記録修正フォーム"""

    class Meta:
        model = EmployeeDailyRecord
        fields = [
            "clock_in",
            "clock_out",
            "status",
        ]

        widgets = {
            "clock_in": forms.DateTimeInput(attrs={"class": "form-control"}),
            "clock_out": forms.DateTimeInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

        labels = {
            "clock_in": "出勤",
            "clock_out": "退勤",
            "status": "ステータス",
        }

    def clean(self):
        cleaned_data = super(forms.ModelForm, self).clean()

        if cleaned_data["status"] in WorkingStatus.HOLIDAY:
            if cleaned_data["clock_in"] or cleaned_data["clock_out"]:
                raise forms.ValidationError(
                    "休日に出勤時間または退勤時間が指定されています"
                )

        if "clock_in" in cleaned_data.keys() and "clock_out" in cleaned_data.keys():
            if cleaned_data["clock_in"] >= cleaned_data["clock_out"]:
                raise forms.ValidationError("出勤時間が退勤時間より後です")

        return cleaned_data


class EditEmployeeForm(forms.ModelForm):
    """
    社員情報変更フォーム
    """

    manager = forms.BooleanField(
        label="管理職",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Employee
        fields = [
            "employee_no",
            "name",
            "join_date",
            "employee_type",
            "department",
        ]

        labels = {
            "employee_no": "社員番号",
            "name": "氏名",
            "join_date": "入社日",
            "employee_type": "雇用種別",
            "department": "所属",
        }
        widgets = {
            "employee_no": forms.NumberInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "join_date": forms.DateInput(attrs={"class": "datepicker form-control"}),
            "employee_type": forms.Select(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super(EditEmployeeForm, self).clean()

        return cleaned_data


class AddEmployeeForm(forms.Form):
    """
    社員情報追加フォーム
    """

    employee_no = forms.IntegerField(
        label="社員番号",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        required=True,
    )
    name = forms.CharField(
        label="氏名",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    join_date = forms.DateField(
        label="入社日",
        widget=forms.TextInput(attrs={"class": "datepicker-future form-control"}),
        initial=datetime.date.today(),
        required=True,
    )
    type = forms.ChoiceField(
        label="雇用種別",
        choices=[(0, "正社員"), (1, "派遣"), (2, "業務委託")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    department = forms.ChoiceField(
        label="所属",
        choices=[(0, "一般"), (1, "開発")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    manager = forms.BooleanField(
        label="管理職",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    # 以下アカウント情報
    accountname = forms.CharField(
        label="アカウント名",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )

    password = forms.CharField(
        label="パスワード",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )

    email = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        required=True,
    )

    def clean(self):
        cleaned_data = super(AddEmployeeForm, self).clean()

        try:
            employee_no = cleaned_data["employee_no"]
            Employee.objects.get(employee_no=employee_no)
            raise forms.ValidationError("社員番号が重複しています")
        except ObjectDoesNotExist:
            pass

        name = cleaned_data["name"]
        if not re.search("(\s|　)+", name):
            raise forms.ValidationError("姓と名の間に空白を入れてください")

        return cleaned_data


class LeaveFromCompanyForm(forms.Form):
    """
    退社処理
    """

    leave_date = forms.DateField(
        label="退社日",
        widget=forms.TextInput(
            attrs={"type": "date", "class": "datepicker-future form-control"}
        ),
        initial=datetime.date.today(),
    )

    def clean(self):
        cleaned_data = super().clean()
        leave_date = cleaned_data.get("leave_date")

        if leave_date and leave_date < datetime.date.today():
            self.add_error("leave_date", "退社日は今日以降の日付を指定してください。")

        return cleaned_data


class ModifyPermissionForm(forms.Form):
    """
    権限変更
    """

    is_staff = forms.BooleanField(
        label="管理者",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check"}),
    )
    enable_view_detail = forms.BooleanField(
        label="自身の勤務実績詳細",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check"}),
    )
    enable_stamp_on_web = forms.BooleanField(
        label="WEBで打刻",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check"}),
    )
    enable_add_staff = forms.BooleanField(
        label="スタッフの追加",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check"}),
    )


class RegisterHolidayForm(forms.ModelForm):
    """休日を登録するフォーム"""

    class Meta:
        model = Holiday
        fields = ["date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"})
        }
        labels = {"date": "日付"}

    def clean(self):
        cleaned_data = super().clean()
        holidays = Holiday.objects.filter(date=cleaned_data["date"])
        if len(holidays) > 0:
            raise forms.ValidationError("すでに登録されています")
        return cleaned_data


class AddSteppingOutForm(forms.Form):
    out_time = forms.TimeField(
        required=False, label="外出", widget=forms.TimeInput(attrs={"type": "time"})
    )

    return_time = forms.TimeField(
        required=False, label="戻り", widget=forms.TimeInput(attrs={"type": "time"})
    )

    def clean(self):
        cleaned_data = super(AddSteppingOutForm, self).clean()
        if not "out_time" in cleaned_data:
            return cleaned_data
        if not "return_time" in cleaned_data:
            return cleaned_data

        if not cleaned_data["out_time"] or not cleaned_data["return_time"]:
            raise forms.ValidationError("時間が指定されていません")

        if cleaned_data["out_time"] >= cleaned_data["return_time"]:
            raise forms.ValidationError(
                "外出と戻りの時間が同じか、戻りの時間が外出時間より速いです"
            )
        return cleaned_data


class WorkingHourForm(forms.ModelForm):
    class Meta:
        model = WorkingHour
        fields = ["category", "begin_time", "end_time", "is_active"]
        widgets = {
            "begin_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "min": "07:00",
                    "max": "22:00",
                    "step": "1800",  # 30分刻み
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "min": "07:00",
                    "max": "22:00",
                    "step": "1800",  # 30分刻み
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        begin_time = cleaned_data.get("begin_time")
        end_time = cleaned_data.get("end_time")

        if begin_time and end_time and begin_time >= end_time:
            raise forms.ValidationError(
                "出社時間は退社時間より前である必要があります。"
            )

        return cleaned_data


class DaySwitchTimeForm(forms.ModelForm):
    class Meta:
        model = DaySwitchTime
        fields = ["switch_time"]
        widgets = {
            "switch_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            )
        }
