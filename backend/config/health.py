from django.http import JsonResponse
from django.db import connection


def health_check(request):
    return JsonResponse({"status": "healthy"})


def readiness_check(request):
    checks = {"status": "ready", "database": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception:
        checks["status"] = "not_ready"
    status_code = 200 if checks["status"] == "ready" else 503
    return JsonResponse(checks, status=status_code)
