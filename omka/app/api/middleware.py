from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from omka.app.core.logging import TraceContext, get_logger

logger = get_logger("api")

_EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico", "/redoc"}


class APILoggingMiddleware(BaseHTTPMiddleware):
    """HTTP 请求/响应日志中间件

    记录每个请求的：方法、路径、状态码、耗时、trace_id
    """

    def __init__(self, app: ASGIApp, *, log_request_body: bool = False, log_response_body: bool = False):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if path in _EXCLUDED_PATHS or path.startswith(("/static/", "/_/")):
            return await call_next(request)

        start = time.perf_counter()
        trace_id = TraceContext.current_id()
        method = request.method

        # 入口日志
        logger.info(
            "[REQ] %s %s | client=%s | trace=%s",
            method, path, _get_client_ip(request), trace_id,
        )

        if self.log_request_body and method in ("POST", "PUT", "PATCH"):
            body = await _read_body(request)
            if body:
                logger.debug("[REQ BODY] %s %s | body=%s", method, path, body[:500])

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = response.status_code

            log_func = logger.info if status < 400 else logger.warning if status < 500 else logger.error
            log_func(
                "[RES] %s %s → %d | elapsed=%.1fms | trace=%s",
                method, path, status, elapsed_ms, trace_id,
            )
            return response

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "[ERR] %s %s → EXCEPTION | elapsed=%.1fms | error=%s: %s | trace=%s",
                method, path, elapsed_ms, type(e).__name__, e, trace_id,
            )
            raise


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _read_body(request: Request) -> str | None:
    try:
        body = await request.body()
        return body.decode("utf-8", errors="replace")[:1000]
    except Exception:
        return None
