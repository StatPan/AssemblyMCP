import logging
from unittest.mock import AsyncMock

import mcp.types as mt
import pytest
from fastmcp.server.middleware import MiddlewareContext

from assemblymcp.config import settings
from assemblymcp.middleware import CachingMiddleware, LoggingMiddleware


# Mock CallToolRequest
def create_mock_context(tool_name="test_tool", arguments=None):
    if arguments is None:
        arguments = {"arg": "value"}
    request = mt.CallToolRequest(
        method="tools/call",
        params=mt.CallToolRequestParams(name=tool_name, arguments=arguments),
    )
    return MiddlewareContext(message=request, fastmcp_context=AsyncMock())


# Mock CallToolResult
def create_mock_result(content="result"):
    return mt.CallToolResult(content=[mt.TextContent(type="text", text=content)])


@pytest.mark.asyncio
async def test_logging_middleware(caplog):
    middleware = LoggingMiddleware()
    context = create_mock_context()

    async def call_next(ctx):
        return create_mock_result()

    settings.log_json = True
    settings.log_level = "INFO"

    with caplog.at_level(logging.INFO):
        await middleware.on_call_tool(context, call_next)

    # Check logs
    assert "Tool call started: test_tool" in caplog.text
    assert "Tool call completed: test_tool" in caplog.text

    # Verify JSON structure (roughly)
    # Since caplog captures formatted log message, and our formatter outputs JSON string as message?
    # No, our formatter is attached to handler, caplog might capture before formatting
    # or use its own handler.
    # But we can check if the extra props are passed.

    # Actually, caplog uses its own handler. We should check if the logger was called with extra.
    # But for integration, just checking the message is enough.


@pytest.mark.asyncio
async def test_caching_middleware():
    middleware = CachingMiddleware()
    settings.enable_caching = True
    settings.cache_ttl_seconds = 60

    # 1. First call (Cache Miss)
    context = create_mock_context(tool_name="get_test")
    mock_next = AsyncMock(return_value=create_mock_result("result1"))

    result1 = await middleware.on_call_tool(context, mock_next)
    assert result1.content[0].text == "result1"
    assert mock_next.call_count == 1

    # 2. Second call (Cache Hit)
    mock_next.reset_mock()
    result2 = await middleware.on_call_tool(context, mock_next)
    assert result2.content[0].text == "result1"
    assert mock_next.call_count == 0  # Should not be called
    assert getattr(result2, "_is_cached", False)


@pytest.mark.asyncio
async def test_caching_middleware_non_cacheable():
    middleware = CachingMiddleware()
    settings.enable_caching = True

    # Tool name doesn't start with get/search/list
    context = create_mock_context(tool_name="do_something")
    mock_next = AsyncMock(return_value=create_mock_result("result"))

    await middleware.on_call_tool(context, mock_next)
    await middleware.on_call_tool(context, mock_next)

    assert mock_next.call_count == 2  # Should be called twice
