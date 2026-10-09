from rest_framework.views import APIView
from rest_framework.response import Response


from reusable_auth.serializers import UserRegistrationSerializer, UserLoginSerializer
from reusable_auth.services import register_user, login_user, get_tokens_for_user


class UserRegistrationView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Respond the same way whether or not the email is already registered,
            # so this endpoint can't be used to discover which emails have accounts.
            # No tokens are returned for the same reason; clients log in afterwards.
            try:
                register_user(**serializer.validated_data)
            except ValueError:
                pass
            return Response({"message": "Registration received. You can now log in."}, status=201)
        return Response(serializer.errors, status=400)


class UserLoginView(APIView):   
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = login_user(**serializer.validated_data)
                tokens = get_tokens_for_user(user)
                return Response({"message": "Login successful.", "tokens": tokens}, status=200)
            except ValueError as e:
                return Response({"error": str(e)}, status=400)
        return Response(serializer.errors, status=400)    
