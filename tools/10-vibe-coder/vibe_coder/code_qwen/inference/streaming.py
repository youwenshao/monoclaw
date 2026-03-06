"""SSE streaming response formatting for CodeQwen endpoints."""

from __future__ import annotations

import json
from typing import AsyncIterator

from starlette.responses import StreamingResponse


async def _format_sse(generator: AsyncIterator[str]) -> AsyncIterator[str]:
    """Wrap token chunks into SSE `data:` frames."""
    async for token in generator:
        payload = json.dumps({"token": token})
        yield f"data: {payload}\n\n"
    yield "data: [DONE]\n\n"


def stream_response(generator: AsyncIterator[str]) -> StreamingResponse:
    """Return a StreamingResponse with text/event-stream content type."""
    return StreamingResponse(
        _format_sse(generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
