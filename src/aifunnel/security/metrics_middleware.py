import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aifunnel.observability import metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        route = request.url.path
        metrics.inc(
            "aifunnel_http_requests_total",
            labels={"method": request.method, "path": route, "status": str(response.status_code)},
        )
        metrics.inc(
            "aifunnel_http_request_duration_seconds_sum",
            labels={"method": request.method, "path": route},
            value=elapsed,
        )
        return response
