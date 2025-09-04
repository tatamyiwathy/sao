from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from common.utils_for_test import TEST_USER, create_client, create_super_user, create_user

from .forms import SignupForm, UserForm, SaoChangePasswordForm
from sao.utils import create_user as create_user_util


class AccountTest(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client = create_client(TEST_USER)

    def test_url(self):
        url = reverse("sao_accounts:list")
        self.assertEqual(url, "/sao_accounts/")




    def test_UserForm_validation(self):
        user = create_user()
        form = UserForm({"username": "foo", "is_active": True}, instance=user)
        self.assertTrue(form.is_valid(), form)

    def test_post_with_nouser(self):
        client = create_client(TEST_USER)
        response = client.get(reverse("sao_accounts:edit", kwargs={"username": "nanashi"}))
        self.assertEqual(response.status_code, 404)

    def test_post_form_normaly(self):
        client = create_client(TEST_USER)
        form = {
            "username": self.user.username,
            "email": self.user.email,
            "is_active": True,
        }
        response = client.post(
            reverse("sao_accounts:edit", kwargs={"username": self.user.username}), form
        )
        self.assertRedirects(response, reverse("sao_accounts:list"))

    def test_post_form_abnormaly(self):
        client = create_client(TEST_USER)
        form = {
            "username": "",
            "email": self.user.email,
            "is_active": True,
        }
        response = client.post(
            reverse("sao_accounts:edit", kwargs={"username": self.user.username}), form
        )
        self.assertTrue(response.status_code == 200)

class AccountViewsTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client = create_client(TEST_USER)
        self.superuser = create_super_user()
        self.client.force_login(self.user)

    def test_account_list_only_active_for_normal_user(self):
        inactive_user = create_user_util(username="inactive", last="", first="", password="pass", email="")
        inactive_user.is_active = False
        url = reverse("sao_accounts:list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        accounts = response.context["accounts"]
        self.assertTrue(all(u.is_active for u in accounts))

    def test_account_list_all_for_superuser(self):
        self.client.force_login(self.superuser)
        inactive_user = create_user_util(username="inactive", last="", first="", password="pass", email="")
        inactive_user.is_active = False
        url = reverse("sao_accounts:list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        usernames = [u.username for u in response.context["accounts"]]
        self.assertIn("inactive", usernames)
        self.assertIn(self.superuser.username, usernames)

    def test_edit_account_get(self):
        url = reverse("sao_accounts:edit", args=[self.user.username])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)

    def test_edit_account_post_valid(self):
        url = reverse("sao_accounts:edit", args=[self.user.username])
        data = {"username": self.user.username, "email": "newemail@example.com"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "newemail@example.com")

    def test_change_password_get(self):
        url = reverse("sao_accounts:change_password", args=[self.user.username])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)

    def test_change_password_form(self):
        url = reverse("sao_accounts:change_password", args=[self.user.username])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["form"], SaoChangePasswordForm)
    
    def test_change_password_form_valid(self):
        form = SaoChangePasswordForm(data={"password": "newsecurepassword", "confirm": ""})
        self.assertFalse(form.is_valid())
        form = SaoChangePasswordForm(data={"password": "newsecurepassword", "confirm": "newsecurepassword"})
        self.assertTrue(form.is_valid())

    def test_change_password_post_valid(self):
        self.client.force_login(self.superuser)
        url = reverse("sao_accounts:change_password", args=[self.user.username])
        data = {"password": "newsecurepassword", "confirm": "newsecurepassword"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newsecurepassword"))
