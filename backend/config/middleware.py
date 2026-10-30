"""Request middleware that only makes sense behind the stack's own ingress."""


class RealIPMiddleware:
    """Replace REMOTE_ADDR with the address the ingress nginx put in X-Real-IP.

    Behind docker-compose.server.yml gunicorn only ever hears from the ingress container,
    so REMOTE_ADDR is always that container and every per-IP rate limit would share one
    bucket. The ingress overwrites X-Real-IP on every request, so the header is trusted.
    Enabled only when USE_X_REAL_IP=true (settings), i.e. where the backend port is not
    published and nothing else can reach gunicorn.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()
        if real_ip:
            request.META['REMOTE_ADDR'] = real_ip
        return self.get_response(request)
