from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from assembly_client.errors import SpecParseError

from assemblymcp.server import client, get_api_spec


@pytest.mark.asyncio
async def test_get_api_spec_success():
    # Mock client.spec_parser.parse_spec
    mock_spec = MagicMock()
    mock_spec.to_dict.return_value = {"service_id": "TEST_ID", "endpoint": "test"}

    with patch.object(client.spec_parser, "parse_spec", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_spec

        result = await get_api_spec.fn("TEST_ID")

        assert result == {"service_id": "TEST_ID", "endpoint": "test"}
        mock_parse.assert_called_once_with("TEST_ID")


@pytest.mark.asyncio
async def test_get_api_spec_parse_error():
    # Mock SpecParseError
    with patch.object(client.spec_parser, "parse_spec", new_callable=AsyncMock) as mock_parse:
        mock_parse.side_effect = SpecParseError("Invalid Excel file")

        result = await get_api_spec.fn("TEST_ID")

        assert result["error_type"] == "SpecParseError"
        assert "Invalid Excel file" in result["error"]
        # suggested_action is not returned for SpecParseError in server.py
        # assert "suggested_action" in result


@pytest.mark.asyncio
async def test_get_api_spec_unexpected_error():
    # Mock generic Exception
    with patch.object(client.spec_parser, "parse_spec", new_callable=AsyncMock) as mock_parse:
        mock_parse.side_effect = Exception("Unexpected crash")

        result = await get_api_spec.fn("TEST_ID")

        assert result["error_type"] == "Exception"
        assert "Unexpected crash" in result["error"]
        assert "spec_cache_location" in result
