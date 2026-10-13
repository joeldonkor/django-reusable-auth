from django.urls import path
from reusable_auth.views import (
    CurrentUserView, DeactivateAccountView, LogoutView, PasswordChangeView, PasswordResetConfirmView,
    PasswordResetView, ResendVerificationView, SessionDetailView, SessionListView, ThrottledTokenRefreshView,
    UserLoginView, UserRegistrationView, VerifyEmailView,
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
    path('auth/me/deactivate/', DeactivateAccountView.as_view(), name='account-deactivate'),

    # Email verification
    path('auth/email/verify/', VerifyEmailView.as_view(), name='email-verify'),
    path('auth/email/verify/resend/', ResendVerificationView.as_view(), name='email-verify-resend'),

    # Passwords
    path('auth/password/change/', PasswordChangeView.as_view(), name='password-change'),
    path('auth/password/reset/', PasswordResetView.as_view(), name='password-reset'),
    path('auth/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
