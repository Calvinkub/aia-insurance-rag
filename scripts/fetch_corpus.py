"""Download the public AIA Thailand English product brochures into data/raw/.

Source list: https://www.aia.co.th/en/our-products/product-list-english
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import requests

BASE = "https://www.aia.co.th"
LIST_URL = f"{BASE}/en/our-products/product-list-english"
HEADERS = {"User-Agent": "Mozilla/5.0 (capstone-rag-research)"}
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    html = requests.get(LIST_URL, headers=HEADERS, timeout=30).text
    paths = sorted(set(re.findall(r'(/content/dam/[^"\']+?\.pdf)', html)))
    if not paths:
        print("no PDF links found; page layout may have changed", file=sys.stderr)
        return 1
    for p in paths:
        name = unquote(p.rsplit("/", 1)[-1]).replace(" ", "_")
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skip   {name}")
            continue
        r = requests.get(BASE + p, headers=HEADERS, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        print(f"fetched {name} ({len(r.content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
