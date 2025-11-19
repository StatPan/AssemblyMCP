"""Tests for spec parser functionality."""

import pytest

from assemblymcp.spec_parser import SpecParser


@pytest.fixture
def spec_parser():
    """Create a spec parser instance."""
    return SpecParser()


@pytest.mark.asyncio
async def test_parse_spec_bill_api(spec_parser):
    """Test parsing spec for bill API."""
    service_id = "OK7XM1000938DS17215"

    spec = spec_parser.parse_spec(service_id)

    assert spec.service_id == service_id
    assert spec.endpoint == "nzmimeepazxkubdpn"
    assert spec.endpoint_url == "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"

    # Check basic params
    assert len(spec.basic_params) == 4
    param_names = [p.name for p in spec.basic_params]
    assert "Key" in param_names
    assert "Type" in param_names
    assert "pIndex" in param_names
    assert "pSize" in param_names

    # Check all basic params are required
    for param in spec.basic_params:
        assert param.required is True

    # Check request params include AGE as required
    age_param = next((p for p in spec.request_params if p.name == "AGE"), None)
    assert age_param is not None
    assert age_param.required is True


@pytest.mark.asyncio
async def test_parse_spec_member_info_api(spec_parser):
    """Test parsing spec for member info API (no required request params)."""
    service_id = "OWSSC6001134T516707"

    spec = spec_parser.parse_spec(service_id)

    assert spec.service_id == service_id
    assert spec.endpoint == "nwvrqwxyaytdsfvhu"

    # This API has no required request parameters (all optional)
    required_params = [p for p in spec.request_params if p.required]
    assert len(required_params) == 0


@pytest.mark.asyncio
async def test_parse_spec_meeting_record_api(spec_parser):
    """Test parsing spec for meeting record API (multiple required params)."""
    service_id = "OO1X9P001017YF13038"

    spec = spec_parser.parse_spec(service_id)

    assert spec.service_id == service_id
    assert spec.endpoint == "nzbyfwhwaoanttzje"

    # This API has DAE_NUM and CONF_DATE as required
    required_param_names = [p.name for p in spec.request_params if p.required]
    assert "DAE_NUM" in required_param_names
    assert "CONF_DATE" in required_param_names


@pytest.mark.asyncio
async def test_spec_caching(spec_parser):
    """Test that specs are cached after first download."""
    service_id = "OK7XM1000938DS17215"

    # First parse - should download
    spec1 = spec_parser.parse_spec(service_id)

    # Second parse - should use cache
    spec2 = spec_parser.parse_spec(service_id)

    assert spec1.endpoint == spec2.endpoint
    assert spec1.service_id == spec2.service_id


@pytest.mark.asyncio
async def test_clear_cache(spec_parser):
    """Test cache clearing functionality."""
    service_id = "OK7XM1000938DS17215"

    # Parse to populate cache
    spec_parser.parse_spec(service_id)

    # Clear specific cache
    spec_parser.clear_cache(service_id)

    # File should be removed
    cache_file = spec_parser.cache_dir / f"{service_id}.xlsx"
    assert not cache_file.exists()


@pytest.mark.asyncio
async def test_parse_old_api_spec(spec_parser):
    """Test parsing old API from 2019."""
    service_id = "OC0RRQ000852J210654"

    spec = spec_parser.parse_spec(service_id)

    assert spec.service_id == service_id
    assert spec.endpoint == "nhllwdafacadantme"
    assert len(spec.basic_params) > 0


@pytest.mark.asyncio
async def test_parse_recent_api_spec(spec_parser):
    """Test parsing recent API from 2025."""
    service_id = "OU8JBT0015343C14378"

    spec = spec_parser.parse_spec(service_id)

    assert spec.service_id == service_id
    assert spec.endpoint == "nkimylolanvseqagq"
    assert len(spec.basic_params) > 0
