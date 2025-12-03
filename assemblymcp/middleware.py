
import time
import json
import logging
from typing import Callable, Awaitable
from datetime import datetime, timezone

from fastmcp.server.middleware import Middleware, MiddlewareContext
import mcp.types as mt

from assemblymcp.config import settings

# Configure Logger
logger = logging.getLogger("assemblymcp")

class JsonFormatter(logging.Formatter):
    """Formatter to output JSON logs for Cloud Run."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
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
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    # Reset handlers to avoid duplication if called multiple times
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(settings.log_level.upper())

class LoggingMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequest],
        call_next: Callable[[MiddlewareContext[mt.CallToolRequest]], Awaitable[mt.CallToolResult]],
    ) -> mt.CallToolResult:
        start_time = time.time()
        tool_name = context.request.params.name
        
        # Log start (only if debug or json to avoid noise in simple mode)
        if settings.log_json or settings.log_level == "DEBUG":
            logger.info(f"Tool call started: {tool_name}", extra={"props": {
                "event": "tool_call_start",
                "tool": tool_name,
                "arguments": context.request.params.arguments
            }})

        try:
            result = await call_next(context)
            duration = time.time() - start_time
            
            is_error = result.isError if hasattr(result, "isError") else False
            
            logger.info(f"Tool call completed: {tool_name}", extra={"props": {
                "event": "tool_call_end",
                "tool": tool_name,
                "duration_seconds": round(duration, 4),
                "is_error": is_error,
                "cached": getattr(result, "_is_cached", False)
            }})
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tool call failed: {tool_name}", extra={"props": {
                "event": "tool_call_error",
                "tool": tool_name,
                "duration_seconds": round(duration, 4),
                "error": str(e)
            }}, exc_info=True)
            raise

class CachingMiddleware(Middleware):
    def __init__(self):
        self.cache = {}
        self.access_order = [] # Simple LRU
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

        tool_name = context.request.params.name
        
        if not self._is_cacheable(tool_name):
            return await call_next(context)

        key = self._get_cache_key(tool_name, context.request.params.arguments)
        
        # Check cache
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                # Mark result as cached for logging
                result = entry["result"]
                # We can't easily attach attributes to Pydantic models without cloning
                # But FastMCP results are Pydantic models.
                # Let's just return it. The logging middleware might not see "cached" flag unless we hack it.
                # Hack: Attach a private attribute to the object instance if possible, or just log here.
                # Since we want centralized logging, let's try to set a flag on the object if it's mutable.
                try:
                    setattr(result, "_is_cached", True)
                except:
                    pass
                
                # Update LRU
                if key in self.access_order:
                    self.access_order.remove(key)
                    self.access_order.append(key)
                
                return result
            else:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)

        # Cache miss
        result = await call_next(context)
        
        is_error = result.isError if hasattr(result, "isError") else False
        if not is_error:
            if len(self.cache) >= self.max_size:
                oldest = self.access_order.pop(0)
                if oldest in self.cache:
                    del self.cache[oldest]
            
            self.cache[key] = {
                "result": result,
                "expires_at": time.time() + self.ttl
            }
            self.access_order.append(key)
            
        return result
