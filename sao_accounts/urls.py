from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "sao_accounts"

urlpatterns = [
    path(
        "login",
        auth_views.LoginView.as_view(template_name="sao_accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.account_list, name="list"),
    path("<slug:username>/edit", views.edit_account, name="edit"),
    path("<slug:username>/change_password", views.change_password, name="change_password"),
]
