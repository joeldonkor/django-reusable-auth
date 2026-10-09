from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from reusable_auth.models import CustomUser
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login






# -----------------------------------------------------------------------------
# Tokens
# -----------------------------------------------------------------------------

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }



# -----------------------------------------------------------------------------
# User registration & login
# -----------------------------------------------------------------------------

@transaction.atomic
def register_user(first_name, last_name, email, password):
    email = CustomUser.objects.normalize_email(email)
    if CustomUser.objects.filter(email=email).exists():
        raise ValueError("A user with this email already exists.")

    try:
        # create_user hashes the password; create() would store it as plain text
        user = CustomUser.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password
        )
    except IntegrityError:
        # Another request registered the same email between the check and the insert
        raise ValueError("A user with this email already exists.")
    return user

def login_user(email, password):
    user = authenticate(email=email, password=password)
    if user is None:
        raise ValueError("Invalid email or password.")
    update_last_login(None, user)
    return user