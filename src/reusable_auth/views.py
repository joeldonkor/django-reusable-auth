from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from reusable_auth.serializers import (
    SessionSerializer, UserLoginSerializer, UserRegistrationSerializer, UserSerializer,
)
from reusable_auth.services import (
    get_active_sessions, get_tokens_for_user, handle_refresh_token_reuse, login_user, record_refresh_rotation,
    register_user, revoke_all_sessions, revoke_session,
)
from reusable_auth.throttles import (
    LoginRateThrottle, LogoutRateThrottle, RefreshRateThrottle, RegisterRateThrottle,
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

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Respond the same way whether or not the email is already registered,
        # so this endpoint can't be used to discover which emails have accounts.
        # No tokens are returned for the same reason; clients log in afterwards.
        try:
            register_user(**serializer.validated_data)
        except ValueError:
            pass
        return Response({"detail": "Registration received. You can now log in."}, status=201)


class UserLoginView(PublicAPIView):
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Raises InvalidCredentials (401) or AccountLocked (429)
        user = login_user(**serializer.validated_data)
        # Same shape as the refresh endpoint: {"access": ..., "refresh": ...}
        return Response(get_tokens_for_user(user))


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [RefreshRateThrottle]

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

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)  # raises InvalidToken (401) for a bad token
        return Response({"detail": "Logged out."})


class CurrentUserView(AuthenticatedAPIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SessionListView(AuthenticatedAPIView):
    def get(self, request):
        """List the user's active sessions (one per logged-in device)."""
        return Response(SessionSerializer(get_active_sessions(request.user), many=True).data)

    def delete(self, request):
        """Log out everywhere."""
        revoke_all_sessions(request.user)
        return Response(status=204)


class SessionDetailView(AuthenticatedAPIView):
    def delete(self, request, session_id):
        # 404 for another user's session too, so ids can't be probed
        if not revoke_session(request.user, session_id):
            raise NotFound()
        return Response(status=204)
