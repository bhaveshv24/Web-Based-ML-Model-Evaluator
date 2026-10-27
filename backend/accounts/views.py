"""Registration and JWT lifecycle endpoints."""

from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import AuditLog
from .serializers import LogoutSerializer, RegisterSerializer, RoleTokenObtainPairSerializer
from .throttles import LoginRateThrottle


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"id": str(user.id), "email": user.email, "role": user.role}, status=201)


class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = RoleTokenObtainPairSerializer
    throttle_classes = (LoginRateThrottle,)

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            AuditLog.objects.create(
                event="LOGIN_FAILED",
                actor_email=str(request.data.get("email", ""))[:254],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            raise


class RefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "Refresh token is invalid.",
                        "details": [],
                    }
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
