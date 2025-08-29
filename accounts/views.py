import logging

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from .forms import UserForm, SaoChangePasswordForm

logger = logging.getLogger("sao")

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


@login_required
def change_password(request, username):
    """パスワード変更"""
    target_user = get_object_or_404(User, username=username)
    
    form = SaoChangePasswordForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            print("form is valid")
            password = form.cleaned_data["password"]
            target_user.set_password(password)
            target_user.save()
            messages.success(request, "パスワードを変更しました")
            logger.info("%sが%sのパスワードを変更しました" % (request.user, target_user.username))
            return redirect("accounts:list")

    return render(
        request,
        "accounts/change_password.html",
        {"form": form, "target_user": target_user},
    )


