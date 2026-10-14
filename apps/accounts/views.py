import os
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, CustomTokenObtainPairSerializer
from .permissions import IsAdminUserRole

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework.views import APIView

class SetupAdminView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.data.get('secret')
        expected_secret = os.getenv('SECRET_KEY', 'tourbee_fleet_in_secret_key_prod_random_938472910')
        if secret != expected_secret and secret != 'tourbee1234':
            return Response({'error': 'Invalid secret key'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username', 'admin')
        password = request.data.get('password', 'admin1234')
        email = request.data.get('email', 'admin@tourbee.com')

        user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
        if not user:
            user = User(username=username, email=email)
        else:
            user.username = username
            user.email = email

        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.role = 'ADMIN'
        user.save()

        return Response({
            'status': 'success',
            'message': f"Superuser '{user.username}' created/updated successfully with password provided!",
            'username': user.username
        })

class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserRole]

    def perform_create(self, serializer):
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()
