"""Analyze API specifications for MCP tool design."""

import json
from pathlib import Path

# Load APIs
with open("specs/by_category/국회의원.json", encoding="utf-8") as f:
    member_apis = json.load(f)
with open("specs/by_category/의정활동별_공개.json", encoding="utf-8") as f:
    activity_apis = json.load(f)

all_apis = member_apis + activity_apis

# Extract key information
print("=== API 분석 ===\n")
print(f"총 {len(all_apis)}개 API\n")

# Analyze by common patterns
output = []
for i, api in enumerate(all_apis, 1):
    info = {
        "번호": i,
        "이름": api["INF_NM"],
        "ID": api["INF_ID"],
        "카테고리": api["CATE_NM"],
        "설명": api["INF_EXP"],
        "명세서URL": api["DDC_URL"],
        "서비스URL": api["SRV_URL"],
        "갱신주기": api["LOAD_NM"],
    }
    output.append(info)

    print(f"{i}. {api['INF_NM']}")
    print(f"   ID: {api['INF_ID']}")
    print(f"   카테고리: {api['CATE_NM']}")
    print(f"   설명: {api['INF_EXP'][:100]}...")
    print()

# Save detailed analysis
output_file = Path("docs/api_detailed_analysis.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n상세 분석 저장: {output_file}")
print("\n다음 단계: 각 API의 명세서를 다운로드하여 파라미터 분석 필요")
