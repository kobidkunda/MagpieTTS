"""Request-id middleware and structured request logging."""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.common import new_request_id

logger = logging.getLogger("magpie.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = new_request_id()
        request.state.request_id = request_id
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            logger.warning("%s %s [%s] failed after %.1f ms",
                           request.method, request.url.path, request_id,
                           (time.time() - start) * 1000.0)
            raise
        ms = (time.time() - start) * 1000.0
        logger.info("%s %s -> %s [%s] %.1f ms", request.method, request.url.path,
                    response.status_code, request_id, ms)
        response.headers["X-Request-ID"] = request_id
        return response
