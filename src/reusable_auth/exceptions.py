from rest_framework import status
from rest_framework.exceptions import APIException, Throttled


# -----------------------------------------------------------------------------
# API errors
# -----------------------------------------------------------------------------
#
# Every error uses DRF's standard shape, so clients handle one format:
#
#   400  {"field": ["message", ...]}   invalid input (serializer validation)
#   401  {"detail": "message"}         bad credentials or invalid token
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
