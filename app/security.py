from __future__ import annotations

import secrets
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            request.session["csrf_token"] = token

        if request.method.upper() not in SAFE_METHODS:
            supplied_token = request.headers.get("x-csrf-token")
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            expected_host = request.headers.get("host")
            source = origin or referer
            same_origin = bool(source and urlparse(source).netloc == expected_host)
            if not same_origin and not secrets.compare_digest(supplied_token or "", token):
                return JSONResponse({"error": "Requisição bloqueada por proteção CSRF."}, status_code=403)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
