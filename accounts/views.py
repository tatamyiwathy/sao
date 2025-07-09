import os

import sao_proj
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from sao_proj.settings import logger

from .forms import SignupForm, UserForm


@login_required
def account_list(request):
    accounts = User.objects.all()
    if True in [
        request.user.permission.enable_regist_event,
        request.user.is_staff,
        request.user.is_superuser,
    ]:
        pass
    else:
        accounts = accounts.filter(is_active=True)
    accounts = accounts.order_by("-is_active")

    return render(request, "accounts/list.html", {"accounts": accounts})


@login_required
def edit_account(request, username):
    u = get_object_or_404(User, username=username)
    if request.method == "POST":
        userform = UserForm(request.POST, instance=u)
        if userform.is_valid() and userform.is_valid():
            userform.save()
            logger.info(
                "%sが%sのプロファイルを変更した" % (request.user, u.username)
            )
            return redirect("accounts:list")

    form = UserForm(instance=u)
    return render(
        request,
        "accounts/edit.html",
        {"form": form, "edituser": u},
    )


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            logger.info("%sのaccountが作られた" % (form.cleaned_data["username"]))
            form.save()

            username = form.cleaned_data["username"]
            user = get_object_or_404(User, username=username)
            password = form.cleaned_data["password"]
            user.set_password(password)
            if user.check_password(password):
                return redirect("accounts:login")
            user.save()
            raise forms.ValidationError("パスワード登録失敗")

    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})
