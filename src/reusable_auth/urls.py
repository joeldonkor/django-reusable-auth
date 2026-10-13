from django.urls import path
from reusable_auth.views import (
    CurrentUserView, LogoutView, SessionDetailView, SessionListView, ThrottledTokenRefreshView,
    UserLoginView, UserRegistrationView,
)


urlpatterns = [
    # Session
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('auth/refresh/', ThrottledTokenRefreshView.as_view(), name='token-refresh'),
    path('auth/logout/', LogoutView.as_view(), name='user-logout'),

    # Account
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/sessions/', SessionListView.as_view(), name='session-list'),
    path('auth/sessions/<int:session_id>/', SessionDetailView.as_view(), name='session-detail'),
]
