import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assemblymcp.spec_parser import SpecParser


@pytest.fixture
def temp_cache_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)


@pytest.fixture
def spec_parser(temp_cache_dir):
    return SpecParser(cache_dir=temp_cache_dir)


@pytest.mark.asyncio
async def test_parse_spec_from_cache(spec_parser, temp_cache_dir):
    # Setup: Create a dummy JSON spec in the cache
    service_id = "TEST_SERVICE_001"
    cached_spec = {
        "service_id": service_id,
        "endpoint": "test_endpoint",
        "endpoint_url": "http://example.com/test_endpoint",
        "basic_params": [],
        "request_params": [],
    }

    cache_file = temp_cache_dir / f"{service_id}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cached_spec, f)

    # Execute
    spec = await spec_parser.parse_spec(service_id)

    # Verify
    assert spec.service_id == service_id
    assert spec.endpoint == "test_endpoint"
    # Ensure we didn't try to download (we can't easily check this without mocking internals,
    # but if download was called it would likely fail or we'd need to mock it)


@pytest.mark.asyncio
async def test_parse_spec_download_and_cache(spec_parser, temp_cache_dir):
    service_id = "TEST_SERVICE_002"

    # Mock Excel content (just random bytes that look like a zip/excel file header)
    # PK\x03\x04 is the zip magic number
    dummy_excel_bytes = b"PK\x03\x04" + b"\x00" * 100

    # Mock httpx.AsyncClient
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = dummy_excel_bytes

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = mock_response

    # Mock openpyxl.load_workbook
    mock_wb = MagicMock()
    mock_ws = MagicMock()
    mock_wb.__getitem__.return_value = mock_ws

    # Mock extraction logic since we don't have a real excel file
    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("openpyxl.load_workbook", return_value=mock_wb),
        patch.object(
            spec_parser,
            "_extract_endpoint_url",
            return_value="http://apis.data.go.kr/test/endpoint",
        ),
    ):
        # Mock row iteration for params
        # Row format: [Name, Type, Description]
        mock_ws.iter_rows.return_value = [
            ["기본인자", None, None],
            ["KEY", "필수", "API Key"],
            ["요청인자", None, None],
            ["PARAM1", "선택", "Parameter 1"],
            ["출력값", None, None],
        ]

        # Execute
        spec = await spec_parser.parse_spec(service_id)

        # Verify Spec
        assert spec.service_id == service_id
        assert spec.endpoint == "endpoint"
        assert len(spec.basic_params) == 1
        assert spec.basic_params[0].name == "KEY"
        assert len(spec.request_params) == 1
        assert spec.request_params[0].name == "PARAM1"

        # Verify Cache Creation
        cache_file = temp_cache_dir / f"{service_id}.json"
        assert cache_file.exists()

        with open(cache_file, encoding="utf-8") as f:
            saved_data = json.load(f)
            assert saved_data["service_id"] == service_id
