from rest_framework import status
from rest_framework.exceptions import APIException, Throttled


# -----------------------------------------------------------------------------
# API errors
# -----------------------------------------------------------------------------
#
# Every error uses DRF's standard shape, so clients handle one format:
#
#   400  {"field": ["message", ...]}   invalid input (serializer validation)
#   400  {"detail": "message"}         invalid or expired emailed link
#   401  {"detail": "message"}         bad credentials or invalid token
#   403  {"detail": "message"}         email not verified yet
#   429  {"detail": "message"}         throttled or locked, plus Retry-After
#
# These are DRF exceptions, so services raise them directly and DRF turns them
# into responses. No custom EXCEPTION_HANDLER is needed, which matters for a
# package: that setting is global and would change the host project's whole API.

class InvalidCredentials(APIException):
    # Not a subclass of AuthenticationFailed on purpose: DRF turns that into a 403
    # on views without authentication classes, like login
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class AccountLocked(Throttled):
    default_detail = "Too many failed login attempts. Try again later."
    default_code = "account_locked"

    def __init__(self, wait):
        # Throttled appends "Expected available in N seconds." to the message
        super().__init__(wait=wait, detail=self.default_detail)


class EmailNotVerified(APIException):
    # Only raised after the password was checked, so it reveals nothing to
    # someone who doesn't already know the password
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Verify your email address before logging in."
    default_code = "email_not_verified"


class InvalidLink(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This link is invalid or has expired."
    default_code = "invalid_link"
