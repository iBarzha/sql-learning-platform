"""Custom ratelimit response for DRF compatibility."""

from django.http import JsonResponse


def ratelimited_response(request, exception):
    """Return a JSON 429 response for rate-limited requests."""
    return JsonResponse(
        {'error': 'Too many requests. Please slow down.'},
        status=429,
    )
