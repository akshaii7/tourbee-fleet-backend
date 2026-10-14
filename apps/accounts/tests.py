from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

class AuthRoleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='test_admin',
            email='admin@tourbee.in',
            password='Password123',
            role=User.Role.ADMIN
        )
        self.driver_user = User.objects.create_user(
            username='test_driver',
            email='driver@tourbee.in',
            password='Password123',
            role=User.Role.DRIVER
        )

    def test_admin_login_and_token(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'test_admin',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['user']['role'], 'ADMIN')
        self.assertTrue(response.data['user']['is_admin'])

    def test_driver_login_and_token(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'test_driver',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('access' in response.data)
        self.assertEqual(response.data['user']['role'], 'DRIVER')
        self.assertTrue(response.data['user']['is_driver'])
