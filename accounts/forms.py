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
        "last_name",
        "first_name",
        "email",
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
