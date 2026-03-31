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
    target_code = "9700006"
    other_code = "9700005"

    mock_client.get_data = AsyncMock(return_value=[
        {"COMMITTEE_NAME": "법제사법위원회", "HR_DEPT_CD": target_code, "HG_NM": "Target Member 1"},
        {"COMMITTEE_NAME": "국회운영위원회", "HR_DEPT_CD": other_code, "HG_NM": "Noise Member 1"},
        {"COMMITTEE_NAME": "법제사법위원회", "HR_DEPT_CD": target_code, "HG_NM": "Target Member 2"},
    ])

    rows = await committee_service.get_committee_members(committee_code=target_code, limit=100)

    assert len(rows) == 2, f"Expected 2 members, got {len(rows)}"
    for row in rows:
        assert row["HR_DEPT_CD"] == target_code
        assert row["COMMITTEE_NAME"] == "법제사법위원회"

    names = [r["HG_NM"] for r in rows]
    assert "Noise Member 1" not in names


@pytest.mark.asyncio
async def test_get_committee_members_filters_incorrect_codes_with_dept_cd_key(committee_service, mock_client):
    """
    Test filtering when the API returns 'DEPT_CD' instead of 'HR_DEPT_CD'.
    """
    target_code = "9700006"
    other_code = "9700005"

    mock_client.get_data = AsyncMock(return_value=[
        {"COMMITTEE_NAME": "법제사법위원회", "DEPT_CD": target_code, "HG_NM": "Target Member"},
        {"COMMITTEE_NAME": "국회운영위원회", "DEPT_CD": other_code, "HG_NM": "Noise Member"},
    ])

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

    mock_client.get_data = AsyncMock(return_value=[
        {"DEPT_CD": other_code, "HG_NM": "Noise Member 1"},
        {"DEPT_CD": other_code, "HG_NM": "Noise Member 2"},
    ])

    rows = await committee_service.get_committee_members(committee_code=target_code)

    assert len(rows) == 0
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_get_committee_members_invalid_korean_name(committee_service, mock_client):
    """
    Test behavior when an invalid Korean committee name is provided (e.g., typo).
    """
    typo_name = "법제사법위훤회"

    mock_client.get_data = AsyncMock(return_value=[
        {"COMMITTEE_NAME": "법제사법위원회", "HG_NM": "Member 1"},
        {"COMMITTEE_NAME": "국회운영위원회", "HG_NM": "Member 2"},
    ])

    rows = await committee_service.get_committee_members(committee_name=typo_name)

    assert len(rows) == 0
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_get_committee_members_api_no_data(committee_service, mock_client):
    """
    Test behavior when API returns no data for a committee name search.
    The service should return a structured error dictionary with suggestions.
    """
    mock_client.get_data = AsyncMock(return_value=[])
    committee_service.get_committee_list = AsyncMock(return_value=[])

    result = await committee_service.get_committee_members(committee_name="없는위원회")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"]["error_type"] == "DATA_NOT_FOUND"
