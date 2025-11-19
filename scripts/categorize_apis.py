"""Categorize APIs by CATE_NM."""

import json
from collections import defaultdict
from pathlib import Path

# Load all pages
all_apis = []
for i in range(1, 4):
    file_path = Path(f"specs/all_apis_p{i}.json")
    if file_path.exists():
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data["OPENSRVAPI"][1]["row"]
        all_apis.extend(rows)

# Categorize
categories = defaultdict(list)
for api in all_apis:
    cate = api.get("CATE_NM", "").split(">")[0]
    categories[cate].append(api)

# Print summary
print(f"Total APIs: {len(all_apis)}\n")
for cate, apis in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"{cate}: {len(apis)}개")

# Save by category
output_dir = Path("specs/by_category")
output_dir.mkdir(exist_ok=True)

for cate, apis in categories.items():
    filename = cate.replace(" ", "_").replace("ㆍ", "_")
    output_file = output_dir / f"{filename}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(apis, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_file}")
