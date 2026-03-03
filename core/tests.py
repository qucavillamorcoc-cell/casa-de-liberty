from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import patch

from .models import OTP


class DashboardViewTests(TestCase):
    def setUp(self):
        # create a staff user and a normal tenant user
        self.staff = User.objects.create_user('staff', 'staff@example.com', 'pw')
        self.staff.is_staff = True
        self.staff.save()
        self.normal = User.objects.create_user('normal', 'normal@example.com', 'pw')

    def test_staff_redirected_to_admin_dashboard(self):
        """Visiting /dashboard as staff should redirect to the staff URL."""
        self.client.login(username='staff', password='pw')
        response = self.client.get(reverse('dashboard'), secure=True)
        self.assertRedirects(response, reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_tenant_sees_tenant_dashboard(self):
        self.client.login(username='normal', password='pw')
        response = self.client.get(reverse('dashboard'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Tenant')

    def test_admin_dashboard_accessible(self):
        self.client.login(username='staff', password='pw')
        response = self.client.get(reverse('admin_dashboard'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_dashboard.html')


class ChangePasswordViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tenant',
            email='tenant@example.com',
            password='OldPass123!'
        )
        self.client.login(username='tenant', password='OldPass123!')

    @patch('core.views.send_otp_email', return_value=True)
    def test_request_otp_shows_verification_form(self, mock_send_otp):
        response = self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': 'OldPass123!',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter OTP Code')
        self.assertTrue(OTP.objects.filter(user=self.user, is_used=False).exists())
        mock_send_otp.assert_called_once()

    @patch('core.views.send_otp_email', return_value=False)
    def test_request_otp_stops_when_email_send_fails(self, mock_send_otp):
        response = self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': 'OldPass123!',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unable to send OTP email right now. Please try again.')
        self.assertNotContains(response, 'Enter OTP Code')
        self.assertFalse(OTP.objects.filter(user=self.user, is_used=False).exists())
        mock_send_otp.assert_called_once()

    def test_request_otp_without_email_redirects_to_settings(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        response = self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': 'OldPass123!',
        }, secure=True)

        self.assertRedirects(response, reverse('settings'), fetch_redirect_response=False)
        self.assertFalse(OTP.objects.filter(user=self.user).exists())

    @patch('core.views.send_otp_email', return_value=True)
    def test_verify_otp_changes_password(self, mock_send_otp):
        self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': 'OldPass123!',
        }, secure=True)

        otp_record = OTP.objects.get(user=self.user)

        response = self.client.post(reverse('change_password'), {
            'action': 'verify_otp',
            'otp_code': otp_record.otp_code,
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }, secure=True)

        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        self.user.refresh_from_db()
        otp_record.refresh_from_db()

        self.assertTrue(self.user.check_password('NewPass123!'))
        self.assertTrue(otp_record.is_used)
        mock_send_otp.assert_called_once()

    def test_verify_otp_without_active_otp_fails(self):
        response = self.client.post(reverse('change_password'), {
            'action': 'verify_otp',
            'otp_code': '000000',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No active OTP found')

    def test_request_otp_requires_current_password(self):
        response = self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': '',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter your current password')

    @patch('core.views.send_otp_email', return_value=True)
    def test_verify_otp_rejects_invalid_otp_format(self, mock_send_otp):
        self.client.post(reverse('change_password'), {
            'action': 'request_otp',
            'current_password': 'OldPass123!',
        }, secure=True)

        response = self.client.post(reverse('change_password'), {
            'action': 'verify_otp',
            'otp_code': '12ab',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OTP must be a 6-digit code')
        mock_send_otp.assert_called_once()


class PasswordResetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reset-user',
            email='reset@example.com',
            password='OldPass123!'
        )

    def test_password_reset_request_requires_username_or_email(self):
        response = self.client.post(reverse('password_reset'), {
            'username_or_email': '',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter your username or email address')

    def test_password_reset_confirm_requires_both_password_fields(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse('password_reset_confirm', args=[uid, token]),
            {'password1': 'NewPass123!', 'password2': ''},
            secure=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please fill in both password fields')

    @patch('core.views.send_password_reset_link_email', return_value=False)
    def test_password_reset_request_handles_email_send_failure(self, mock_send_email):
        response = self.client.post(reverse('password_reset'), {
            'username_or_email': 'reset-user',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unable to send reset email right now. Please try again later.')
        mock_send_email.assert_called_once()


class RegisterViewTests(TestCase):
    def test_register_requires_email(self):
        response = self.client.post(reverse('register'), {
            'username': 'noemail',
            'password': 'SomePass123!',
            'email': '',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Username, email, and password are required')
        self.assertFalse(User.objects.filter(username='noemail').exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user('existing', 'same@example.com', 'OldPass123!')

        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'password': 'SomePass123!',
            'email': 'same@example.com',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email is already registered')
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_register_rejects_invalid_email(self):
        response = self.client.post(reverse('register'), {
            'username': 'invalidmail',
            'password': 'SomePass123!',
            'email': 'not-an-email',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a valid email address')
        self.assertFalse(User.objects.filter(username='invalidmail').exists())


class LoginViewTests(TestCase):
    def test_login_requires_both_fields(self):
        response = self.client.post(reverse('login'), {
            'username': '',
            'password': '',
        }, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter both username and password')
