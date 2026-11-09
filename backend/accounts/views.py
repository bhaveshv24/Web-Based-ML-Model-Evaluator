"""Registration and JWT lifecycle endpoints."""

from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import AuditLog, User
from .permissions import IsAdmin
from .serializers import (
    AdminUserSerializer,
    AuditLogSerializer,
    LogoutSerializer,
    RegisterSerializer,
    RoleTokenObtainPairSerializer,
    UserActivationSerializer,
)
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
            token = RefreshToken(serializer.validated_data["refresh"])
            if str(token["user_id"]) != str(request.user.pk):
                raise TokenError("Refresh token does not belong to this session.")
            token.blacklist()
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


class AdminUserView(APIView):
    """API-23: an ADMIN activates or deactivates an account (UC-12, BR-08).

    Users are deactivated, never deleted, so their audit history is kept. Deactivation also
    blacklists every outstanding refresh token, so the account cannot mint new access tokens;
    SimpleJWT already rejects access tokens of inactive users.
    """

    permission_classes = (IsAdmin,)

    def patch(self, request, id):
        target = get_object_or_404(User, id=id)
        serializer = UserActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_active = serializer.validated_data["is_active"]
        if target.pk == request.user.pk and not is_active:
            raise ValidationError({"is_active": ["Admins cannot deactivate their own account."]})
        with transaction.atomic():
            target.is_active = is_active
            target.save(update_fields=["is_active"])
            if not is_active:
                for token in OutstandingToken.objects.filter(user=target):
                    BlacklistedToken.objects.get_or_create(token=token)
            AuditLog.objects.create(
                event="USER_ACTIVATED" if is_active else "USER_DEACTIVATED",
                user=request.user,
                actor_email=request.user.email,
                ip_address=request.META.get("REMOTE_ADDR"),
                metadata={"target_user_id": str(target.pk)},
            )
        return Response(
            {"id": str(target.pk), "email": target.email, "role": target.role,
             "is_active": target.is_active}
        )


class AdminUserListView(generics.ListAPIView):
    permission_classes = (IsAdmin,)
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        return User.objects.filter(email__icontains=query).order_by("email")


class AdminAuditListView(generics.ListAPIView):
    permission_classes = (IsAdmin,)
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.order_by("-created_at", "-pk")
