from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from reusable_auth.serializers import UserLoginSerializer, UserRegistrationSerializer, UserSerializer
from reusable_auth.services import get_tokens_for_user, login_user, register_user
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


class CurrentUserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
