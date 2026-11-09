"""Authentication throttles keyed by both IP and normalized email."""

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        email = str(request.data.get("email", "")).strip().lower()
        return self.cache_format % {"scope": self.scope, "ident": f"{ident}:{email}"}


class UploadRateThrottle(UserRateThrottle):
    """SEC-007: model and dataset uploads are rate limited per authenticated user."""

    scope = "upload"
