import time
import logging
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)

class RequestTimingMiddleware:
    """
    Lightweight timing middleware that logs request method, path, response status,
    total execution time in milliseconds, and the number of database queries (when DEBUG).
    Adds an X-Response-Time-Ms header to the HTTP response.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.perf_counter()
        initial_queries = len(connection.queries) if settings.DEBUG else 0

        response = self.get_response(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if settings.DEBUG:
            num_queries = len(connection.queries) - initial_queries
            msg = f"[PERF] {request.method} {request.path} {response.status_code} - {duration_ms}ms ({num_queries} DB queries)"
        else:
            msg = f"[PERF] {request.method} {request.path} {response.status_code} - {duration_ms}ms"

        logger.info(msg)
        print(msg)

        response['X-Response-Time-Ms'] = str(duration_ms)
        return response
