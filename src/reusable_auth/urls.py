from django.urls import path
from reusable_auth.views import UserRegistrationView, UserLoginView, ThrottledTokenRefreshView


urlpatterns = [
    # Session
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('auth/refresh/', ThrottledTokenRefreshView.as_view(), name='token-refresh'),
]