"""Analyze API parameters by testing sample APIs."""

import json

import httpx

# Load categorized APIs
with open("specs/by_category/국회의원.json", encoding="utf-8") as f:
    member_apis = json.load(f)
with open("specs/by_category/의정활동별_공개.json", encoding="utf-8") as f:
    activity_apis = json.load(f)

# Sample representative APIs from different functional groups
samples = [
    {"name": "국회의원 인적사항", "id": "OWSSC6001134T516707", "group": "의원정보"},
    {"name": "국회의원 발의법률안", "id": "OK7XM1000938DS17215", "group": "의원활동"},
    {"name": "국회의원 본회의 표결정보", "id": "OPR1MQ000998LC12535", "group": "의원활동"},
    {"name": "본회의 회의록", "id": "OO1X9P001017YF13038", "group": "회의록"},
    {"name": "위원회 회의록", "id": "OR137O001023MZ19321", "group": "회의록"},
    {"name": "법률안 제안이유 및 주요내용", "id": "OS46YD0012559515463", "group": "의안정보"},
    {"name": "위원회 현황 정보", "id": None, "group": "위원회정보"},
    {"name": "본회의 일정", "id": None, "group": "일정정보"},
]


def find_endpoint(api_id, source_list):
    """Extract endpoint from INF_ID."""
    # Endpoint naming pattern varies, try to deduce from ID
    # For now, return the ID itself as a placeholder
    api_info = next((a for a in source_list if a["INF_ID"] == api_id), None)
    if api_info:
        # Try to extract from SRV_URL
        srv_url = api_info.get("SRV_URL", "")
        # URL format: .../selectAPIServicePage.do/XXXXX
        if "/" in srv_url:
            endpoint = srv_url.split("/")[-1]
            return endpoint
    return api_id


def test_api(endpoint, api_key="sample"):
    """Test API and return structure."""
    base_url = f"https://open.assembly.go.kr/portal/openapi/{endpoint}"
    params = {"KEY": api_key, "Type": "json", "pIndex": 1, "pSize": 1}

    try:
        response = httpx.get(base_url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        return {"error": str(e)}


# Test each sample
print("=== API 파라미터 분석 ===\n")

for sample in samples:
    api_id = sample["id"]
    if not api_id:
        # Find by name
        all_apis = member_apis + activity_apis
        api_info = next((a for a in all_apis if a["INF_NM"] == sample["name"]), None)
        if not api_info:
            print(f"[{sample['group']}] {sample['name']}: NOT FOUND\n")
            continue
        api_id = api_info["INF_ID"]

    endpoint = find_endpoint(api_id, member_apis + activity_apis)

    print(f"[{sample['group']}] {sample['name']}")
    print(f"  Endpoint: {endpoint}")
    print("  Testing...")

    result = test_api(endpoint)
    if "error" in result:
        print(f"  Error: {result['error']}\n")
    else:
        # Extract response structure
        if isinstance(result, list) and len(result) > 0:
            root_key = list(result[0].keys())[0]
            print(f"  Root key: {root_key}")
            if len(result) > 1 and "row" in result[1]:
                row = result[1]["row"]
                if row and len(row) > 0:
                    fields = list(row[0].keys())
                    print(f"  Fields: {', '.join(fields[:10])}")
            print()
        else:
            print(f"  Unexpected format: {type(result)}\n")

print("\n다음: 분석 결과를 바탕으로 MCP 도구 설계 문서 작성")
