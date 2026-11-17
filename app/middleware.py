import logging
import time
from typing import Callable

import httpx
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest

from app.prompts import build_system_prompt

logger = logging.getLogger("saferoute")
MAX_TOOL_CHARS = 8000
MAX_ATTEMPTS = 3
RETRYABLE = (httpx.HTTPError, ConnectionError, TimeoutError)  # network problems only


@dynamic_prompt
def trip_prompt(request: ModelRequest) -> str:
    """Rebuilds the system prompt on every model call so the current date/time is always correct."""
    return build_system_prompt()


@wrap_model_call
def model_timer(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    start = time.perf_counter()
    response = handler(request)
    ms = (time.perf_counter() - start) * 1000
    tokens = None
    try:
        usage = getattr(response.result[-1], "usage_metadata", None) or {}
        tokens = usage.get("total_tokens")
    except Exception:
        pass
    logger.info("model_call %.0f ms, tokens=%s", ms, tokens)
    return response


def _error_message(request: ToolCallRequest, text: str) -> ToolMessage:
    return ToolMessage(
        content=text,
        tool_call_id=request.tool_call["id"],
        name=request.tool_call["name"],
        status="error",
    )


@wrap_tool_call
def tool_guard(request: ToolCallRequest, handler):
    """Retries network errors only. Any other error is logged with a traceback and shown to the model in full."""
    name = request.tool_call["name"]
    start = time.perf_counter()
    result = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = handler(request)
            break
        except RETRYABLE as exc:
            logger.warning("tool %s network error (attempt %d/%d): %s", name, attempt, MAX_ATTEMPTS, exc)
            if attempt == MAX_ATTEMPTS:
                return _error_message(
                    request,
                    f"ERROR in tool '{name}': network problem after {MAX_ATTEMPTS} attempts ({exc}). "
                    "Tell the user this could not be checked.",
                )
            time.sleep(1.5 * attempt)
        except Exception as exc:
            logger.exception("tool %s failed", name)
            return _error_message(
                request,
                f"ERROR in tool '{name}': {type(exc).__name__}: {exc}. "
                "Do not repeat the same call with the same arguments. "
                "Do not guess this information; tell the user it could not be checked.",
            )

    if isinstance(result, ToolMessage) and isinstance(result.content, str) and len(result.content) > MAX_TOOL_CHARS:
        result = result.model_copy(update={"content": result.content[:MAX_TOOL_CHARS] + " ...[truncated]"})
    logger.info("tool %s ok in %.0f ms", name, (time.perf_counter() - start) * 1000)
    return result


def build_middleware() -> list:
    return [
        trip_prompt,
        model_timer,
        tool_guard,
        ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
        ModelCallLimitMiddleware(run_limit=12, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=20),
    ]