from django.urls import path
from reusable_auth.views import UserRegistrationView, UserLoginView
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    # Session
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]