import json

from assemblymcp.ux import failure_marker, marker, parse_claims, workflow_contract


def test_failure_marker_shape():
    result = failure_marker(
        "not_found",
        "No rows.",
        attempted_queries=[{"tool": "search_bills"}],
        source_tools=["search_bills"],
        suggested_next_queries=[{"tool": "list_api_services"}],
    )

    assert result["ok"] is False
    assert result["marker"] == "[NOT_FOUND]"
    assert result["message"].startswith("[NOT_FOUND]")
    assert result["attempted_queries"][0]["tool"] == "search_bills"
    assert "invent" in result["llm_instruction"]


def test_marker_accepts_known_and_unknown_values():
    assert marker("ambiguous") == "[AMBIGUOUS]"
    assert marker("[CUSTOM]") == "[CUSTOM]"
    assert marker("custom") == "[CUSTOM]"


def test_parse_claims_accepts_json_object_list_and_plain_text():
    assert parse_claims('{"type": "bill", "value": "간호법안"}') == [{"type": "bill", "value": "간호법안"}]
    assert parse_claims(json.dumps([{"type": "member", "value": "홍길동"}])) == [{"type": "member", "value": "홍길동"}]
    assert parse_claims("법제사법위원회") == [{"type": "auto", "value": "법제사법위원회", "source": "plain_text"}]


def test_workflow_contract_lists_public_tools_and_failure_markers():
    contract = workflow_contract()

    assert "verify_legislative_claims" in contract["public_workflow_tools"]
    assert "issue_brief" in contract["public_workflow_tools"]
    assert contract["failure_markers"]["verify_failed"] == "[VERIFY_FAILED]"
    assert any(path["intent"] == "주장/인용 검증" for path in contract["recommended_paths"])
