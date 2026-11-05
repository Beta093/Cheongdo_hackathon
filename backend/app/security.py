import re
import time
from collections import deque
from threading import RLock

from starlette.responses import JSONResponse

from backend.app.schemas import MAX_IMAGE_BASE64


class RateLimiter:
    def __init__(self, session_limit: int, ip_limit: int, window: int):
        self.session_limit = session_limit
        self.ip_limit = ip_limit
        self.window = window
        self.buckets: dict[str, deque[float]] = {}
        self.lock = RLock()

    def allow(self, session: str, ip: str) -> bool:
        with self.lock:
            now = time.monotonic()
            cutoff = now - self.window
            for key in list(self.buckets):
                bucket = self.buckets[key]
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self.buckets[key]
            keys = [(f"session:{session}", self.session_limit), (f"ip:{ip}", self.ip_limit)]
            if len(self.buckets) >= 10000 or any(len(self.buckets.get(key, ())) >= limit
                                               for key, limit in keys):
                return False
            for key, _ in keys:
                self.buckets.setdefault(key, deque()).append(now)
            return True


class SecurityMiddleware:
    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; "
                     b"connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
                ]
                if scope["path"].startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        if scope["method"] == "POST" and scope["path"].startswith("/api/"):
            content_type = dict(scope.get("headers", [])).get(b"content-type", b"").split(b";", 1)[0]
            image_chat = (content_type == b"application/json" and
                          bool(re.fullmatch(r"/api/farms/[^/]+/chat", scope["path"])))
            limit = MAX_IMAGE_BASE64 + self.max_body_bytes if image_chat else self.max_body_bytes
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    await JSONResponse({"detail": "요청이 너무 큽니다."}, status_code=422 if image_chat else 413)(
                        scope, receive, secure_send)
                    return
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, secure_send)
        else:
            await self.app(scope, receive, secure_send)
