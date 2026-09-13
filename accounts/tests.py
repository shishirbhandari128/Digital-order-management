from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User, UserRole


class UserRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse('accounts:register')
        self.admin = User.objects.create_superuser(
            username='admin', password='AdminPass123!', name='Admin', role=UserRole.ADMINISTRATOR,
        )
        self.payload = {
            'username': 'kitchen1',
            'password': 'KitchenPass123!',
            'name': 'Kitchen One',
            'role': UserRole.KITCHEN_STAFF,
        }

    def test_registration_requires_admin(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_register_staff_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        user = User.objects.get(username='kitchen1')
        self.assertTrue(user.check_password('KitchenPass123!'))
        self.assertEqual(user.role, UserRole.KITCHEN_STAFF)

    def test_registration_rejects_invalid_role(self):
        self.client.force_authenticate(self.admin)
        payload = {**self.payload, 'role': 'patient'}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_weak_password(self):
        self.client.force_authenticate(self.admin)
        payload = {**self.payload, 'password': '123'}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginLogoutTests(APITestCase):
    def setUp(self):
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')
        self.refresh_url = reverse('token_refresh')
        self.user = User.objects.create_user(
            username='kitchen1', password='KitchenPass123!', name='Kitchen One', role=UserRole.KITCHEN_STAFF,
        )

    def test_login_returns_tokens_and_user(self):
        response = self.client.post(self.login_url, {'username': 'kitchen1', 'password': 'KitchenPass123!'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'kitchen1')
        self.assertEqual(response.data['user']['role'], UserRole.KITCHEN_STAFF)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(self.login_url, {'username': 'kitchen1', 'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        response = self.client.post(self.logout_url, {'refresh': 'irrelevant'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(self.login_url, {'username': 'kitchen1', 'password': 'KitchenPass123!'})
        access = login_response.data['access']
        refresh = login_response.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        logout_response = self.client.post(self.logout_url, {'refresh': refresh})
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        self.client.credentials()
        refresh_response = self.client.post(self.refresh_url, {'refresh': refresh})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_invalid_refresh_token(self):
        login_response = self.client.post(self.login_url, {'username': 'kitchen1', 'password': 'KitchenPass123!'})
        access = login_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.post(self.logout_url, {'refresh': 'not-a-real-token'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
