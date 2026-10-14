"""Role-based permissions shared by protected APIs."""

from rest_framework.permissions import BasePermission

from .models import AuditLog, User


def _audit_denial(request, required_role):
    AuditLog.objects.create(
        event="AUTHORIZATION_DENIED",
        user=request.user if request.user.is_authenticated else None,
        actor_email=getattr(request.user, "email", ""),
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={"required_role": required_role, "path": request.path},
    )


class IsEvaluator(BasePermission):
    message = "Evaluator role required."

    def has_permission(self, request, view):
        allowed = request.user.is_authenticated and request.user.role in {
            User.Role.EVALUATOR,
            User.Role.ADMIN,
        }
        if request.user.is_authenticated and not allowed:
            _audit_denial(request, User.Role.EVALUATOR)
        return allowed
