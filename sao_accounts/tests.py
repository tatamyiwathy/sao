from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from common.utils_for_test import TEST_USER, create_client, create_user

from .forms import SignupForm, UserForm


class AccountTest(TestCase):
    def setUp(self):
        self.user = create_user()

        self.urls_with_authed = [
        ]

        self.urls_with_noauth = [
            reverse("sao_accounts:list"),
            reverse("sao_accounts:edit", kwargs={"username": TEST_USER["username"]}),
            reverse("sao_accounts:list"),
        ]

    def test_create_user(self):

        user = User.objects.create(username="foo")
        self.assertTrue(user)

    def test_form_validation(self):

        user = User.objects.create(username="foo", is_active=True)
        form = UserForm({"username": "foo", "is_active": True}, instance=user)
        self.assertTrue(form.is_valid(), form)

    def test_view_without_login(self):
        client = Client()
        for url in self.urls_with_noauth:
            response = client.get(url)
            self.assertFalse(response.status_code == 200)
        for url in self.urls_with_authed:
            response = client.get(url)
            self.assertTrue(response.status_code == 200)

    def test_view_with_login(self):
        client = create_client(TEST_USER)
        for url in self.urls_with_noauth:
            response = client.get(url)
            self.assertTrue(response.status_code == 200)
        for url in self.urls_with_authed:
            response = client.get(url)
            self.assertTrue(response.status_code == 200)

    def test_post_with_nouser(self):
        client = create_client(TEST_USER)
        response = client.get(reverse("sao_accounts:edit", kwargs={"username": "nanashi"}))
        self.assertEqual(response.status_code, 404)

    def test_post_form_noabnormaly(self):
        client = create_client(TEST_USER)
        form = {
            "username": self.user.username,
            "email": self.user.email,
            "ntd_email": "",
            "is_active": True,
        }
        response = client.post(
            reverse("sao_accounts:edit", kwargs={"username": self.user}), form
        )
        self.assertRedirects(response, reverse("sao_accounts:list"))

    def test_post_form_abnormaly(self):
        client = create_client(TEST_USER)
        form = {
            "username": "",
            "email": self.user.email,
            "ntd_email": "",
            "is_active": True,
        }
        response = client.post(
            reverse("sao_accounts:edit", kwargs={"username": self.user}), form
        )
        self.assertTrue(response.status_code == 200)


class SignupTest(TestCase):
    from common.utils_for_test import TEST_USER

    def setUp(self):
        self.context = {
            "username": TEST_USER["username"],
            "password": TEST_USER["password"],
            "last_name": TEST_USER["last_name"],
            "first_name": TEST_USER["first_name"],
            "email": TEST_USER["email"],
        }

    def test_form_ok(self):
        form = SignupForm(self.context)
        self.assertTrue(form.is_valid(), form)

    def test_form_passwd_less_min(self):
        self.context["password"] = "test"
        form = SignupForm(self.context)
        form.is_valid()
        self.assertFormError(
            form,
            "password",
            "この値が少なくとも 6 文字以上であることを確認してください (4 文字になっています)。",
        )
