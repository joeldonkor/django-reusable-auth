from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from reusable_auth.models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser']
        read_only_fields = fields


class UserRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        # Run the host project's AUTH_PASSWORD_VALIDATORS. An unsaved user is passed
        # so UserAttributeSimilarityValidator can reject passwords like the email/name.
        user = CustomUser(
            first_name=attrs['first_name'],
            last_name=attrs['last_name'],
            email=attrs['email'],
        )
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        return attrs


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
 