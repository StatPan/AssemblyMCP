"""Workflow UX helpers for AssemblyMCP public tools."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

FAILURE_MARKERS = {
    "not_found": "[NOT_FOUND]",
    "ambiguous": "[AMBIGUOUS]",
    "verify_failed": "[VERIFY_FAILED]",
    "api_failed": "[API_FAILED]",
    "partial": "[PARTIAL]",
}

PUBLIC_WORKFLOW_TOOLS = [
    "get_legislative_research_kit",
    "verify_legislative_claims",
    "issue_brief",
    "bill_timeline",
    "legislative_impact_map",
    "watch_action_plan",
]

ENTITY_ALIASES = {
    "bill": "bill",
    "law": "bill",
    "act": "bill",
    "의안": "bill",
    "법안": "bill",
    "법률안": "bill",
    "member": "member",
    "representative": "member",
    "lawmaker": "member",
    "의원": "member",
    "국회의원": "member",
    "committee": "committee",
    "위원회": "committee",
    "vote": "vote",
    "voting": "vote",
    "표결": "vote",
    "auto": "auto",
}


def marker(kind: str) -> str:
    """Return a stable machine-readable failure marker."""
    return FAILURE_MARKERS.get(kind, kind if kind.startswith("[") else f"[{kind.upper()}]")


def failure_marker(
    kind: str,
    message: str,
    *,
    attempted_queries: Iterable[Any] | None = None,
    source_tools: Iterable[str] | None = None,
    suggested_next_queries: Iterable[Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured failure object that LLM clients can route on."""
    resolved = marker(kind)
    result: dict[str, Any] = {
        "ok": False,
        "marker": resolved,
        "message": f"{resolved} {message}",
        "source_tools": list(source_tools or []),
        "attempted_queries": list(attempted_queries or []),
        "suggested_next_queries": list(suggested_next_queries or []),
        "llm_instruction": (
            "Do not invent missing legislative facts. Surface this marker, explain what was checked, "
            "and use suggested_next_queries if more evidence is needed."
        ),
    }
    if details:
        result["details"] = details
    return result


def normalize_text(value: Any) -> str:
    """Normalize text for exact-ish comparisons without losing Korean content."""
    return re.sub(r"\s+", "", str(value or "")).casefold()


def normalize_claim_type(value: Any) -> str:
    """Normalize a user-facing claim/citation type into a supported entity type."""
    return ENTITY_ALIASES.get(normalize_text(value) if value else "auto", "auto")


def normalize_date(value: Any) -> str | None:
    """Convert common National Assembly date shapes to YYYY-MM-DD where possible."""
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return candidate
    digits = re.sub(r"[^0-9]", "", candidate)
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return candidate


def to_public_data(value: Any) -> Any:
    """Convert pydantic models and nested values into JSON-serializable data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return {k: to_public_data(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_public_data(v) for v in value]
    return value


def parse_claims(citations_or_text: str) -> list[dict[str, Any]]:
    """Parse JSON claims or fall back to a single auto claim from plain text."""
    text = (citations_or_text or "").strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [{"type": "auto", "value": text, "source": "plain_text"}]

    if isinstance(parsed, list):
        return [item if isinstance(item, dict) else {"type": "auto", "value": item} for item in parsed]
    if isinstance(parsed, dict):
        if isinstance(parsed.get("claims"), list):
            return [item if isinstance(item, dict) else {"type": "auto", "value": item} for item in parsed["claims"]]
        return [parsed]
    return [{"type": "auto", "value": parsed}]


def compact_bill(value: Any) -> dict[str, Any]:
    """Return the bill fields that are useful in workflow outputs."""
    data = to_public_data(value) or {}
    return {
        key: data.get(key)
        for key in [
            "BILL_ID",
            "BILL_NO",
            "BILL_NAME",
            "PROPOSER",
            "PRIMARY_PROPOSER",
            "PROC_STATUS",
            "CURR_COMMITTEE",
            "PROPOSE_DT",
            "COMMITTEE_DT",
            "PROC_DT",
            "LINK_URL",
        ]
        if data.get(key) is not None
    }


def workflow_contract() -> dict[str, Any]:
    """Describe the workflow-first public MCP surface."""
    return {
        "name": "AssemblyMCP Legislative Research Kit",
        "version": "2026-05-31",
        "public_workflow_tools": PUBLIC_WORKFLOW_TOOLS,
        "naming_contract": {
            "verbs": {
                "verify_": "검증: 인용/주장과 국회 데이터의 일치 여부를 확인",
                "issue_": "이슈 브리핑: 여러 API를 조합해 현황 요약",
                "bill_": "의안 단위 워크플로",
                "legislative_": "입법 생태계/관계 지도",
                "watch_": "모니터링 계획",
                "get_": "단일 자료 조회 또는 안내",
            },
            "compatibility": "Existing tools remain available; workflow tools add a clearer first-call interface.",
        },
        "failure_markers": FAILURE_MARKERS,
        "recommended_paths": [
            {
                "intent": "주장/인용 검증",
                "tools": ["verify_legislative_claims", "get_bill_details", "get_member_info", "get_committee_info"],
            },
            {
                "intent": "주제별 입법 브리핑",
                "tools": ["issue_brief", "bill_timeline", "get_legislative_reports", "search_meetings"],
            },
            {
                "intent": "관계도/영향도 작성",
                "tools": ["legislative_impact_map", "get_representative_report", "get_bill_voting_results"],
            },
            {
                "intent": "지속 모니터링",
                "tools": ["watch_action_plan", "search_bills", "search_meetings", "get_plenary_schedule"],
            },
            {
                "intent": "고수준 툴에 없는 API 탐색",
                "tools": ["list_api_services", "get_api_spec", "call_api_raw"],
            },
        ],
    }
