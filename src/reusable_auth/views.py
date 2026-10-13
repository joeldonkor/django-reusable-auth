from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from reusable_auth.conf import get_setting
from reusable_auth.emails import send_account_exists_email, send_password_reset_email, send_verification_email
from reusable_auth.schema import DetailSerializer, TokensSerializer, errors, extend_schema
from reusable_auth.serializers import (
    EmailSerializer, LinkSerializer, PasswordChangeSerializer, PasswordResetConfirmSerializer, PasswordSerializer,
    SessionSerializer, UserLoginSerializer, UserRegistrationSerializer, UserSerializer,
)
from reusable_auth.services import (
    change_password, deactivate_account, get_active_sessions, get_tokens_for_user, get_user_for_email,
    handle_refresh_token_reuse, login_user, record_refresh_rotation, register_user, reset_password,
    revoke_all_sessions, revoke_session, verify_email,
)
from reusable_auth.throttles import (
    AccountChangeRateThrottle, LinkConfirmRateThrottle, LoginRateThrottle, LogoutRateThrottle,
    PasswordResetRateThrottle, RefreshRateThrottle, RegisterRateThrottle, VerificationResendRateThrottle,
)


# Every view sets its authentication and permission classes explicitly instead of
# inheriting REST_FRAMEWORK defaults. A host project with
# DEFAULT_PERMISSION_CLASSES = [IsAuthenticated] would otherwise lock everyone
# out of login and register.


class PublicAPIView(APIView):
    # No authentication: a client sending a stale "Authorization: Bearer ..." header
    # would otherwise get a 401 from JWTAuthentication before it could log in again
    authentication_classes = []
    permission_classes = [AllowAny]


class AuthenticatedAPIView(APIView):
    # JWT explicitly, even if the host project defaults to session auth
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class UserRegistrationView(PublicAPIView):
    throttle_classes = [RegisterRateThrottle]

    @extend_schema(tags=["auth"], request=UserRegistrationSerializer, responses={201: DetailSerializer, **errors(429)})
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Respond the same way whether or not the email is already registered,
        # so this endpoint can't be used to discover which emails have accounts.
        # No tokens are returned for the same reason; clients log in afterwards.
        # The owner of an existing account is told by email instead.
        try:
            user = register_user(**serializer.validated_data)
        except ValueError:
            existing = get_user_for_email(serializer.validated_data["email"])
            if existing is not None:
                send_account_exists_email(existing)
        else:
            if get_setting("REQUIRE_EMAIL_VERIFICATION"):
                send_verification_email(user)

        if get_setting("REQUIRE_EMAIL_VERIFICATION"):
            detail = "Registration received. Check your email to verify your account."
        else:
            detail = "Registration received. You can now log in."
        return Response({"detail": detail}, status=201)


class UserLoginView(PublicAPIView):
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["auth"], request=UserLoginSerializer, responses={200: TokensSerializer, **errors(401, 403, 429)})
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Raises InvalidCredentials (401) or AccountLocked (429)
        user = login_user(**serializer.validated_data)
        # Same shape as the refresh endpoint: {"access": ..., "refresh": ...}
        return Response(get_tokens_for_user(user))


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [RefreshRateThrottle]

    @extend_schema(tags=["auth"], responses={200: TokensSerializer, **errors(401, 429)})
    def post(self, request, *args, **kwargs):
        raw_token = request.data.get("refresh") if isinstance(request.data, dict) else None
        try:
            response = super().post(request, *args, **kwargs)
        except InvalidToken as exc:
            if not handle_refresh_token_reuse(raw_token):
                raise
            # Return the 401 instead of raising it. With ATOMIC_REQUESTS, DRF rolls
            # back the request's transaction on exceptions, which would undo the
            # session revocation that just happened.
            return Response(
                exc.detail, status=exc.status_code,
                headers={"WWW-Authenticate": self.get_authenticate_header(request)},
            )

        if jwt_settings.ROTATE_REFRESH_TOKENS:
            record_refresh_rotation(raw_token)
        return response


class LogoutView(TokenBlacklistView):
    """
    Blacklist a refresh token so it can't be used again.

    Doesn't require an access token: the refresh token itself proves the client
    holds the session, and the access token has often expired by the time a user
    logs out. Access tokens can't be revoked and stay valid until they expire,
    so keep ACCESS_TOKEN_LIFETIME short.
    """
    throttle_classes = [LogoutRateThrottle]

    @extend_schema(tags=["auth"], responses={200: DetailSerializer, **errors(401, 429)})
    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)  # raises InvalidToken (401) for a bad token
        return Response({"detail": "Logged out."})


class CurrentUserView(AuthenticatedAPIView):
    @extend_schema(tags=["account"], responses={200: UserSerializer, **errors(401)})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class DeactivateAccountView(AuthenticatedAPIView):
    throttle_classes = [AccountChangeRateThrottle]

    @extend_schema(tags=["account"], request=PasswordSerializer, responses={204: None, **errors(401, 429)})
    def post(self, request):
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deactivate_account(request.user, **serializer.validated_data)
        return Response(status=204)


class SessionListView(AuthenticatedAPIView):
    @extend_schema(tags=["sessions"], responses={200: SessionSerializer(many=True), **errors(401)})
    def get(self, request):
        """List the user's active sessions (one per logged-in device)."""
        return Response(SessionSerializer(get_active_sessions(request.user), many=True).data)

    @extend_schema(
        tags=["sessions"], operation_id="sessions_revoke_all", summary="Log out everywhere",
        responses={204: None, **errors(401)},
    )
    def delete(self, request):
        """Log out everywhere."""
        revoke_all_sessions(request.user)
        return Response(status=204)


class SessionDetailView(AuthenticatedAPIView):
    @extend_schema(tags=["sessions"], operation_id="sessions_revoke", responses={204: None, **errors(401, 404)})
    def delete(self, request, session_id):
        # 404 for another user's session too, so ids can't be probed
        if not revoke_session(request.user, session_id):
            raise NotFound()
        return Response(status=204)


# -----------------------------------------------------------------------------
# Email verification
# -----------------------------------------------------------------------------

class VerifyEmailView(PublicAPIView):
    throttle_classes = [LinkConfirmRateThrottle]

    @extend_schema(tags=["email"], request=LinkSerializer, responses={200: DetailSerializer, **errors(400, 429)})
    def post(self, request):
        serializer = LinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_email(**serializer.validated_data)  # raises InvalidLink (400)
        return Response({"detail": "Email verified. You can now log in."})


class ResendVerificationView(PublicAPIView):
    throttle_classes = [VerificationResendRateThrottle]

    @extend_schema(tags=["email"], request=EmailSerializer, responses={200: DetailSerializer, **errors(429)})
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_for_email(serializer.validated_data["email"], unverified=True)
        if user is not None:
            send_verification_email(user)
        # Same answer whether or not the email exists or is already verified
        return Response({"detail": "If that email needs verifying, a new link is on its way."})


# -----------------------------------------------------------------------------
# Passwords
# -----------------------------------------------------------------------------

class PasswordChangeView(AuthenticatedAPIView):
    throttle_classes = [AccountChangeRateThrottle]

    @extend_schema(tags=["password"], request=PasswordChangeSerializer, responses={200: TokensSerializer, **errors(401, 429)})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Every session is logged out, so this device gets fresh tokens
        return Response(change_password(request.user, **serializer.validated_data))


class PasswordResetView(PublicAPIView):
    throttle_classes = [PasswordResetRateThrottle]

    @extend_schema(tags=["password"], request=EmailSerializer, responses={200: DetailSerializer, **errors(429)})
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_for_email(serializer.validated_data["email"])
        if user is not None:
            send_password_reset_email(user)
        # Same answer whether or not the email has an account
        return Response({"detail": "If that email has an account, a reset link is on its way."})


class PasswordResetConfirmView(PublicAPIView):
    throttle_classes = [LinkConfirmRateThrottle]

    @extend_schema(
        tags=["password"], request=PasswordResetConfirmSerializer,
        responses={200: DetailSerializer, **errors(400, 429)},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_password(**serializer.validated_data)  # raises InvalidLink (400)
        return Response({"detail": "Password reset. You can now log in."})
