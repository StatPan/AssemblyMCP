from unittest.mock import AsyncMock, MagicMock

import pytest

from assemblymcp.services import CommitteeService


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def committee_service(mock_client):
    return CommitteeService(mock_client)


@pytest.mark.asyncio
async def test_get_committee_members_filters_incorrect_codes(committee_service, mock_client):
    """
    Test that get_committee_members correctly filters out members from other committees
    when searched by committee_code, even if the API returns them.
    """
    target_code = "9700006"  # Target: 법제사법위원회
    other_code = "9700005"  # Noise: 국회운영위원회

    # Simulate API returning mixed results (Bug reproduction scenario)
    mock_response = {
        "OCAJQ4001000LI18751": [
            {
                "head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}}],
                "row": [
                    {
                        "COMMITTEE_NAME": "법제사법위원회",
                        "HR_DEPT_CD": target_code,
                        "HG_NM": "Target Member 1",
                    },
                    {
                        "COMMITTEE_NAME": "국회운영위원회",  # Should be filtered out
                        "HR_DEPT_CD": other_code,
                        "HG_NM": "Noise Member 1",
                    },
                    {
                        "COMMITTEE_NAME": "법제사법위원회",
                        "HR_DEPT_CD": target_code,
                        "HG_NM": "Target Member 2",
                    },
                ],
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Call the service
    rows = await committee_service.get_committee_members(committee_code=target_code, limit=100)

    # Verification
    assert len(rows) == 2, f"Expected 2 members, got {len(rows)}"
    for row in rows:
        assert row["HR_DEPT_CD"] == target_code
        assert row["COMMITTEE_NAME"] == "법제사법위원회"

    # Ensure invalid member is NOT in the list
    names = [r["HG_NM"] for r in rows]
    assert "Noise Member 1" not in names


@pytest.mark.asyncio
async def test_get_committee_members_filters_incorrect_codes_with_dept_cd_key(committee_service, mock_client):
    """
    Test filtering when the API returns 'DEPT_CD' instead of 'HR_DEPT_CD'.
    """
    target_code = "9700006"
    other_code = "9700005"

    mock_response = {
        "row": [
            {
                "COMMITTEE_NAME": "법제사법위원회",
                "DEPT_CD": target_code,  # Key variation
                "HG_NM": "Target Member",
            },
            {
                "COMMITTEE_NAME": "국회운영위원회",
                "DEPT_CD": other_code,
                "HG_NM": "Noise Member",
            },
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    rows = await committee_service.get_committee_members(committee_code=target_code)

    assert len(rows) == 1
    assert rows[0]["DEPT_CD"] == target_code
    assert rows[0]["HG_NM"] == "Target Member"


@pytest.mark.asyncio
async def test_get_committee_members_empty_result_handling(committee_service, mock_client):
    """
    Test that if filtering removes all results, an empty list is returned.
    """
    target_code = "9700006"
    other_code = "9700005"

    # API returns only wrong data
    mock_response = {
        "row": [
            {"DEPT_CD": other_code, "HG_NM": "Noise Member 1"},
            {"DEPT_CD": other_code, "HG_NM": "Noise Member 2"},
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    rows = await committee_service.get_committee_members(committee_code=target_code)

    assert len(rows) == 0
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_get_committee_members_invalid_korean_name(committee_service, mock_client):
    """
    Test behavior when an invalid Korean committee name is provided (e.g., typo).
    Scenario: API returns some data (ignoring the bad name param) but client-side filtering
    should remove everything because names don't match.
    """
    typo_name = "법제사법위훤회"  # Typo

    # API ignores the name and returns data for "법제사법위원회" (Best case assumption for API behavior)
    # OR API returns everything. In either case, filtering should clear it.
    mock_response = {
        "row": [
            {"COMMITTEE_NAME": "법제사법위원회", "HG_NM": "Member 1"},  # Mismatch
            {"COMMITTEE_NAME": "국회운영위원회", "HG_NM": "Member 2"},  # Mismatch
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    rows = await committee_service.get_committee_members(committee_name=typo_name)

    # Since "법제사법위훤회" is not in any "COMMITTEE_NAME", result should be empty
    assert len(rows) == 0
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_get_committee_members_api_no_data(committee_service, mock_client):
    """
    Test behavior when API explicitly returns INFO-200 (No Data).
    The service should return a structured error dictionary with suggestions.
    """
    mock_response = {
        "OCAJQ4001000LI18751": [
            {
                "head": [
                    {"list_total_count": 0},
                    {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}},
                ]
            }
        ]
    }
    mock_client.get_data = AsyncMock(return_value=mock_response)

    # Mocking list_api_services for suggestion generation inside error handling
    # The service calls self.get_committee_list recursively for suggestions
    committee_service.get_committee_list = AsyncMock(return_value=[])

    result = await committee_service.get_committee_members(committee_name="없는위원회")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"]["error_type"] == "DATA_NOT_FOUND"
