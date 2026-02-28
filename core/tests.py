from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


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
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_tenant_sees_tenant_dashboard(self):
        self.client.login(username='normal', password='pw')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Tenant')

    def test_admin_dashboard_accessible(self):
        self.client.login(username='staff', password='pw')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_dashboard.html')
