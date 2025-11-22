"""Reusable JSON schemas for MCP tool responses."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from assemblymcp.models import Bill, BillDetail


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of model-generated schema without mutating the source."""
    cleaned = deepcopy(schema)
    cleaned.pop("title", None)
    return cleaned


_BILL_SCHEMA = _clean_schema(Bill.model_json_schema())
_BILL_DETAIL_SCHEMA = _clean_schema(BillDetail.model_json_schema())


def _wrap_result_schema(result_schema: dict[str, Any]) -> dict[str, Any]:
    """Wraps the schema in FastMCP's expected structured_content shape."""
    return {
        "type": "object",
        "properties": {"result": result_schema},
        "required": ["result"],
        "x-fastmcp-wrap-result": True,
    }


def bill_list_output_schema() -> dict[str, Any]:
    """Schema describing a list of bills."""
    return _wrap_result_schema({"type": "array", "items": deepcopy(_BILL_SCHEMA)})


def bill_detail_output_schema() -> dict[str, Any]:
    """Schema describing a bill detail object (or null)."""
    return _wrap_result_schema({"anyOf": [deepcopy(_BILL_DETAIL_SCHEMA), {"type": "null"}]})
