"""Custom ratelimit response for DRF compatibility."""

from django.http import JsonResponse
from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

TOO_MANY = 'Too many requests. Please slow down.'


def ratelimited_response(request, exception):
    """Return a JSON 429 response for rate-limited requests."""
    return JsonResponse({'error': TOO_MANY}, status=429)


def exception_handler(exc, context):
    """Ratelimited subclasses PermissionDenied, which DRF would report as 403."""
    if isinstance(exc, Ratelimited):
        return Response({'detail': TOO_MANY, 'error': TOO_MANY},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    return drf_exception_handler(exc, context)
