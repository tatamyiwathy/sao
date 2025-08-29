from django import forms
from django.contrib.auth.models import User


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        label="パスワード（6文字以上）",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        min_length=6,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "last_name",
            "first_name",
            "email",
        ]


class UserForm(forms.ModelForm):
    field_order = [
        "username",
        "email",
        "last_name",
        "first_name",
        "is_active",
    ]

    class Meta:
        model = User
        fields = {"is_active", "username", "email", "last_name", "first_name"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

class SaoChangePasswordForm(forms.Form):
    """
    パスワード変更フォーム
    """

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="新しいパスワード",
    )
    confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="確認",
    )

    def clean(self):
        cleaned_data = super(SaoChangePasswordForm, self).clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm")

        if not password:
            self.add_error("password", "パスワードを入力してください")
        if not confirm:
            self.add_error("confirm", "確認用パスワードを入力してください")

        if password != confirm:
            raise forms.ValidationError("パスワードが一致しません")
        
        return cleaned_data
