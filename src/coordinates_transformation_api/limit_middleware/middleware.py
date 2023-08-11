import asyncio
import typing
from typing import Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[Response]
]


class ContentSizeExceeded(Exception):
    pass


class TimeoutMiddleware(BaseHTTPMiddleware):
    #  based on https://github.com/encode/starlette/issues/890#issuecomment-926062125
    def __init__(
        self,
        app: ASGIApp,
        dispatch: DispatchFunction | None = None,
        timeout_seconds: Optional[int] = None,
    ):
        BaseHTTPMiddleware.__init__(self, app, dispatch=dispatch)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        try:
            response = await asyncio.wait_for(
                call_next(request), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                {
                    "type": "about:blank",
                    "title": "Gateway Timeout",
                    "status": 504,
                    "detail": f"The server timed-out procesing the request, processing the request took longer than {self.timeout_seconds} seconds",
                },
                status_code=504,
            )  # need to manully set the error response instead of raising an HTTPException, since this is happening outside the context of the rfc7807 middleware
        return response


class ContentSizeLimitMiddleware:
    # based on https://github.com/steinnes/content-size-limit-asgi/tree/master
    def __init__(self, app: ASGIApp, max_content_size: Optional[int] = None):
        self.app = app
        self.max_content_size = max_content_size
        self.received = 0

    def receive_wrapper(self, receive: Receive):
        received = 0

        async def inner():
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or self.max_content_size is None:
                return message

            body_len = len(message.get("body", b""))
            received += body_len
            if received > self.max_content_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Maximum content size limit ({self.max_content_size}) exceeded ({body_len} bytes read)",
                )
            return message

        return inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        _receive = self.receive_wrapper(receive)
        await self.app(scope, _receive, send)
