# Excel Spec Parser Documentation

## Overview

The Korean National Assembly Open API uses Service IDs that are different from the actual API endpoints. To resolve the correct endpoint, we must parse Excel specification files provided by the API.

## Problem

- **Service ID**: `OK7XM1000938DS17215` (identifier)
- **Actual Endpoint**: `nzmimeepazxkubdpn` (different!)
- **Challenge**: No direct way to map Service ID to endpoint without parsing Excel specs

## Solution

The `SpecParser` class automatically:
1. Downloads Excel spec files from the API's DDC_URL
2. Extracts the actual endpoint URL
3. Parses required and optional parameters
4. Caches specs to avoid repeated downloads

## Excel Spec Format

All Excel specs follow a consistent format (validated across 2019-2025):

```
Row 2:  오픈 API 명세서
Row 4:  (API Name)
Row 6:  • 요청주소
Row 7:  - https://open.assembly.go.kr/portal/openapi/{endpoint}
Row 9:  • 요청제한횟수
Row 12: • 기본인자  (Common params: KEY, Type, pIndex, pSize)
Row 19: • 요청인자  (API-specific params with 필수/선택)
Row 24+: • 출력값   (Response fields)
```

## Usage

### Basic Usage

```python
from assemblymcp.spec_parser import SpecParser

parser = SpecParser()

# Parse a spec
spec = parser.parse_spec("OK7XM1000938DS17215")

print(f"Endpoint: {spec.endpoint}")  # nzmimeepazxkubdpn
print(f"URL: {spec.endpoint_url}")   # https://...

# Check required parameters
required_params = [p.name for p in spec.request_params if p.required]
print(f"Required: {required_params}")  # ['AGE']
```

### With AssemblyAPIClient

The client automatically uses the spec parser:

```python
from src.client.assembly_api import AssemblyAPIClient

client = AssemblyAPIClient(api_key="your_key")

# Automatically resolves endpoint from spec
data = await client.get_data(
    service_id="OK7XM1000938DS17215",
    params={"AGE": "21"}  # Required parameter
)
```

### Custom Cache Directory

```python
from pathlib import Path

parser = SpecParser(cache_dir=Path("/custom/cache/dir"))
```

### Cache Management

```python
# Clear specific service cache
parser.clear_cache("OK7XM1000938DS17215")

# Clear all cache
parser.clear_cache()
```

## API Specification Object

The `APISpec` dataclass contains:

```python
@dataclass
class APISpec:
    service_id: str           # e.g., "OK7XM1000938DS17215"
    endpoint: str             # e.g., "nzmimeepazxkubdpn"
    endpoint_url: str         # Full URL
    basic_params: list[APIParameter]    # Common params (KEY, Type, etc.)
    request_params: list[APIParameter]  # API-specific params
```

### API Parameter Object

```python
@dataclass
class APIParameter:
    name: str          # Parameter name
    type: str          # e.g., "STRING(필수)"
    required: bool     # True if 필수, False if 선택
    description: str   # Korean description
```

## Examples

### Example 1: Bill API (국회의원 발의법률안)

```python
spec = parser.parse_spec("OK7XM1000938DS17215")

# Result:
# - endpoint: "nzmimeepazxkubdpn"
# - Required param: AGE (대수)
# - Optional params: BILL_ID, BILL_NO, BILL_NAME, etc.
```

### Example 2: Member Info API (국회의원 인적사항)

```python
spec = parser.parse_spec("OWSSC6001134T516707")

# Result:
# - endpoint: "nwvrqwxyaytdsfvhu"
# - No required params (all optional)
# - Optional params: HG_NM, POLY_NM, ORIG_NM, etc.
```

### Example 3: Meeting Record API (본회의 회의록)

```python
spec = parser.parse_spec("OO1X9P001017YF13038")

# Result:
# - endpoint: "nzbyfwhwaoanttzje"
# - Required params: DAE_NUM, CONF_DATE
# - Optional params: TITLE, CLASS_NAME, etc.
```

## Validation

Tested across:
- **10+ different APIs**
- **Time range**: 2019 to 2025 (6 years)
- **Categories**: 의원활동, 의원정보, 회의록, 주제별 공개
- **Success rate**: 90%+ (some APIs have restricted spec access)

## Error Handling

```python
from assemblymcp.spec_parser import SpecParseError

try:
    spec = parser.parse_spec("INVALID_ID")
except SpecParseError as e:
    print(f"Failed to parse spec: {e}")
```

Common errors:
- `SpecParseError`: Spec download or parsing failed
- Excel file not accessible (403, 404)
- Malformed Excel structure

## Performance

- **First call**: ~1-2 seconds (download + parse)
- **Cached calls**: ~50ms (load from disk)
- **Cache location**: `/tmp/assembly_specs/` (configurable)

## Implementation Details

### Download Process

1. Construct DDC_URL: `https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId={service_id}&infSeq=2`
2. Send GET request with User-Agent header
3. Save to cache: `{cache_dir}/{service_id}.xlsx`
4. Validate file size (must be > 100 bytes)

### Parsing Process

1. Load Excel with `openpyxl`
2. Search for "요청주소" keyword (row 1-30)
3. Extract URL from next row
4. Parse "기본인자" section (stop at "요청인자")
5. Parse "요청인자" section (stop at "출력값")
6. Identify 필수/선택 from type string

## Future Improvements

- Parallel spec downloads for multiple services
- Spec version tracking and update notifications
- Output field parsing (currently only params)
- Automatic cache refresh based on LOAD_DTTM
