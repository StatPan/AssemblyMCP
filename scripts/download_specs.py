"""Download API specifications for analysis."""

import json
import time
from pathlib import Path

import httpx

# Load APIs
with open("specs/by_category/국회의원.json", encoding="utf-8") as f:
    member_apis = json.load(f)
with open("specs/by_category/의정활동별_공개.json", encoding="utf-8") as f:
    activity_apis = json.load(f)

# Sample representative APIs
samples = [
    ("국회의원 인적사항", "OWSSC6001134T516707", member_apis),
    ("국회의원 발의법률안", "OK7XM1000938DS17215", member_apis),
    ("국회의원 본회의 표결정보", "OPR1MQ000998LC12535", member_apis),
    ("본회의 회의록", None, activity_apis),
    ("위원회 회의록", None, activity_apis),
    ("법률안 제안이유 및 주요내용", None, activity_apis),
]

# Create output directory
output_dir = Path("specs/api_specs")
output_dir.mkdir(exist_ok=True)

# Download specifications
for name, inf_id, source in samples:
    if inf_id is None:
        # Find by name
        api = next((a for a in source if a["INF_NM"] == name), None)
        if not api:
            print(f"Not found: {name}")
            continue
        inf_id = api["INF_ID"]
    else:
        api = next((a for a in source if a["INF_ID"] == inf_id), None)

    ddc_url = api["DDC_URL"]
    print(f"Downloading: {name} ({inf_id})")
    print(f"  URL: {ddc_url}")

    try:
        response = httpx.get(ddc_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()

        # Save specification
        filename = f"{inf_id}_{name.replace(' ', '_')}.txt"
        output_file = output_dir / filename
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)

        print(f"  Saved: {output_file}\n")
        time.sleep(1)  # Be polite

    except Exception as e:
        print(f"  Error: {e}\n")

print("Complete")
