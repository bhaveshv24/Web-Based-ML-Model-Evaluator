"""Sanitized, consistent API error responses."""

from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler


def _flatten_details(value):
    if isinstance(value, dict):
        return [{"field": key, "messages": _flatten_details(item)} for key, item in value.items()]
    if isinstance(value, list):
        return [_flatten_details(item) for item in value]
    if isinstance(value, ErrorDetail):
        return str(value)
    return value


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    default_message = "Request could not be completed."
    if response.status_code == 401:
        default_message = "Authentication credentials were not accepted."
    elif response.status_code == 403:
        default_message = "You do not have permission to perform this action."
    elif response.status_code == 404:
        default_message = "Resource not found."

    response.data = {
        "error": {
            "code": getattr(exc, "default_code", "API_ERROR").upper(),
            "message": default_message,
            "details": _flatten_details(response.data),
        }
    }
    return response
