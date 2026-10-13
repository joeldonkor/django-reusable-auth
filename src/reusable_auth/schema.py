from rest_framework import serializers

# -----------------------------------------------------------------------------
# OpenAPI schema (optional)
# -----------------------------------------------------------------------------
#
# The views are annotated for drf-spectacular, but it isn't a required
# dependency: without it, extend_schema does nothing and the package works the
# same. Host projects that want API docs install it with
# `pip install django-reusable-auth[openapi]`.

try:
    from drf_spectacular.utils import extend_schema
except ImportError:  # pragma: no cover - exercised only without drf-spectacular
    def extend_schema(*args, **kwargs):
        return lambda view_method: view_method


# Response shapes. These only describe responses for the docs; the views build
# the response data directly.

class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class TokensSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


def errors(*statuses):
    """Document error responses shaped {"detail": ...}. Field validation errors (400) aren't listed."""
    return {status: DetailSerializer for status in statuses}
