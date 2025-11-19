import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assemblymcp.spec_parser import SpecParser


@pytest.fixture
def spec_parser(tmp_path):
    return SpecParser(cache_dir=tmp_path)


def test_calculate_file_hash(spec_parser, tmp_path):
    test_file = tmp_path / "test.txt"
    content = b"hello world"
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert spec_parser.calculate_file_hash(test_file) == expected_hash


@pytest.mark.asyncio
async def test_download_if_changed_new_file(spec_parser):
    service_id = "TEST_SERVICE"
    content = b"new content" * 20  # Make it > 100 bytes

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = content
        mock_get.return_value = mock_response

        updated = await spec_parser.download_if_changed(service_id)

        assert updated is True
        assert (spec_parser.cache_dir / f"{service_id}.xlsx").exists()
        assert (spec_parser.cache_dir / f"{service_id}.xlsx").read_bytes() == content


@pytest.mark.asyncio
async def test_download_if_changed_unchanged(spec_parser):
    service_id = "TEST_SERVICE"
    content = b"existing content" * 20  # Make it > 100 bytes

    # Create existing cache
    cache_file = spec_parser.cache_dir / f"{service_id}.xlsx"
    cache_file.write_bytes(content)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = content
        mock_get.return_value = mock_response

        updated = await spec_parser.download_if_changed(service_id)

        assert updated is False
        assert cache_file.read_bytes() == content


@pytest.mark.asyncio
async def test_download_if_changed_updated(spec_parser):
    service_id = "TEST_SERVICE"
    old_content = b"old content" * 20
    new_content = b"new content" * 20

    # Create existing cache
    cache_file = spec_parser.cache_dir / f"{service_id}.xlsx"
    cache_file.write_bytes(old_content)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = new_content
        mock_get.return_value = mock_response


@pytest.mark.asyncio
async def test_fetch_master_list(spec_parser):
    # Mock response data
    mock_data = {
        "OOBAOA001213RL17443": [
            {"head": [{"list_total_count": 1}]},
            {"row": [{"INF_ID": "TEST_ID", "INF_NM": "Test API"}]},
        ]
    }

    # Mock parser
    mock_parser = MagicMock()
    mock_parser.download_if_changed = AsyncMock(return_value=False)
    mock_spec = MagicMock()
    mock_spec.endpoint = "mock_endpoint"
    mock_parser.parse_spec = AsyncMock(return_value=mock_spec)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response

        import sys

        sys.path.append("scripts")
        from sync_specs import fetch_master_list

        rows = await fetch_master_list("fake_key", mock_parser)
        assert len(rows) == 1
        assert rows[0]["INF_ID"] == "TEST_ID"


@pytest.mark.asyncio
async def test_save_master_list(tmp_path):
    import sys

    sys.path.append("scripts")
    from sync_specs import save_master_list

    rows = [{"INF_ID": "TEST_ID", "INF_NM": "Test API"}]
    save_master_list(rows, tmp_path)

    output_file = tmp_path / "all_apis.json"
    assert output_file.exists()

    import json

    with open(output_file) as f:
        data = json.load(f)
        assert data["OPENSRVAPI"][1]["row"][0]["INF_ID"] == "TEST_ID"
