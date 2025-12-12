import asyncio
import contextlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import mcp.types as mt
from fastmcp.server.middleware import Middleware, MiddlewareContext

from assemblymcp.config import settings
from assemblymcp.initialization import ensure_master_list

# Configure Logger
logger = logging.getLogger("assemblymcp")


class JsonFormatter(logging.Formatter):
    """Formatter to output JSON logs for Cloud Run."""

    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "path": record.pathname,
            "lineno": record.lineno,
        }
        if hasattr(record, "props"):
            log_record.update(record.props)
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)


def configure_logging():
    """Configure the root logger based on settings."""
    handler = logging.StreamHandler()

    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # Reset handlers to avoid duplication if called multiple times
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(settings.log_level.upper())


def _extract_tool_info(message: mt.CallToolRequest | mt.CallToolRequestParams) -> tuple[str, dict]:
    """
    Extract tool name and arguments from the message.
    Handles both CallToolRequest (has .params) and CallToolRequestParams (is params).
    """
    if hasattr(message, "params"):
        return message.params.name, message.params.arguments
    return message.name, message.arguments


class InitializationMiddleware(Middleware):
    def __init__(self, client):
        self.client = client
        self._initialized = False
        self._lock = asyncio.Lock()

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequest],
        call_next: Callable[[MiddlewareContext[mt.CallToolRequest]], Awaitable[mt.CallToolResult]],
    ) -> mt.CallToolResult:
        if self.client and not self._initialized:
            async with self._lock:
                if not self._initialized:
                    try:
                        await ensure_master_list(self.client)
                        self._initialized = True
                    except Exception as e:
                        logger.critical(f"Failed to initialize master list: {e}")
                        raise RuntimeError(f"Server initialization failed: {e}") from e
        return await call_next(context)


class LoggingMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequest],
        call_next: Callable[[MiddlewareContext[mt.CallToolRequest]], Awaitable[mt.CallToolResult]],
    ) -> mt.CallToolResult:
        tool_name, arguments = _extract_tool_info(context.message)

        start_time = time.time()

        # Log start (only if debug or json to avoid noise in simple mode)
        if settings.log_json or settings.log_level == "DEBUG":
            logger.info(
                f"Tool call started: {tool_name}",
                extra={
                    "props": {
                        "event": "tool_call_start",
                        "tool": tool_name,
                        "arguments": arguments,
                    }
                },
            )

        try:
            result = await call_next(context)
            duration = time.time() - start_time

            is_error = result.isError if hasattr(result, "isError") else False

            logger.info(
                f"Tool call completed: {tool_name}",
                extra={
                    "props": {
                        "event": "tool_call_end",
                        "tool": tool_name,
                        "duration_seconds": round(duration, 4),
                        "is_error": is_error,
                        "cached": getattr(result, "_is_cached", False),
                    }
                },
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Tool call failed: {tool_name}",
                extra={
                    "props": {
                        "event": "tool_call_error",
                        "tool": tool_name,
                        "duration_seconds": round(duration, 4),
                        "error": str(e),
                    }
                },
                exc_info=True,
            )
            raise


class CachingMiddleware(Middleware):
    def __init__(self):
        self.cache = OrderedDict()
        self.ttl = settings.cache_ttl_seconds
        self.max_size = settings.cache_max_size

    def _get_cache_key(self, tool_name: str, arguments: dict | None) -> str:
        args_str = json.dumps(arguments, sort_keys=True) if arguments else ""
        return f"{tool_name}:{args_str}"

    def _is_cacheable(self, tool_name: str) -> bool:
        return tool_name.startswith(("get_", "search_", "list_"))

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequest],
        call_next: Callable[[MiddlewareContext[mt.CallToolRequest]], Awaitable[mt.CallToolResult]],
    ) -> mt.CallToolResult:
        if not settings.enable_caching:
            return await call_next(context)

        tool_name, arguments = _extract_tool_info(context.message)

        if not self._is_cacheable(tool_name):
            return await call_next(context)

        key = self._get_cache_key(tool_name, arguments)

        # Check cache
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                # Mark result as cached for logging
                result = entry["result"]
                # Move to end (most recently used)
                self.cache.move_to_end(key)

                with contextlib.suppress(AttributeError, TypeError):
                    result._is_cached = True

                return result
            else:
                # Expired
                del self.cache[key]

        # Cache miss
        result = await call_next(context)

        is_error = result.isError if hasattr(result, "isError") else False
        if not is_error:
            # Evict if full
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)  # Remove first (least recently used)

            self.cache[key] = {"result": result, "expires_at": time.time() + self.ttl}

        return result
