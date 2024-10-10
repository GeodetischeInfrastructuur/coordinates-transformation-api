import asyncio
import typing
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[[Request, RequestResponseEndpoint], typing.Awaitable[Response]]


class ContentSizeExceededError(Exception):
    pass


class TimeoutMiddleware(BaseHTTPMiddleware):
    #  based on https://github.com/encode/starlette/issues/890#issuecomment-926062125
    def __init__(
        self: "TimeoutMiddleware",
        app: ASGIApp,
        dispatch: DispatchFunction | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        BaseHTTPMiddleware.__init__(self, app, dispatch=dispatch)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self: "TimeoutMiddleware", request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except TimeoutError:
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


Message = typing.MutableMapping[str, typing.Any]


class ContentSizeLimitMiddleware:
    # based on https://github.com/steinnes/content-size-limit-asgi/tree/master
    def __init__(
        self: "ContentSizeLimitMiddleware",
        app: ASGIApp,
        max_content_size: int | None = None,
    ) -> None:
        self.app = app
        self.max_content_size = max_content_size
        self.received = 0

    def receive_wrapper(self: "ContentSizeLimitMiddleware", receive: Receive) -> Callable:
        received = 0

        async def inner() -> Message:
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

    async def __call__(self: "ContentSizeLimitMiddleware", scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        _receive = self.receive_wrapper(receive)
        await self.app(scope, _receive, send)
