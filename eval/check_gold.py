"""Sanity-check the gold set against the source text: every evidence quote must occur on a cited page,
and unanswerable questions must not have their key terms in the corpus."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
norm = lambda s: " ".join(s.split()).lower()
pages = [json.loads(l) for l in (ROOT / "data" / "pages.jsonl").read_text().splitlines()]
gold = [json.loads(l) for l in (ROOT / "eval" / "gold.jsonl").read_text().splitlines()]
bad = 0
for g in gold:
    if g["answerable"]:
        ok = [norm(g["evidence"]) in norm(p["text"]) for p in pages if p["product"] == g["product"] and p["page"] in g["pages"]]
        if not any(ok):
            print("EVIDENCE NOT FOUND", g["id"], g["evidence"][:70]); bad += 1
corpus = norm(" ".join(p["text"] for p in pages))
for term in ["covid", "reward tier", "settlement ratio", "chiang mai", "mobile app", "gold status"]:
    if term in corpus:
        print("WARNING: unanswerable term present in corpus:", term); bad += 1
print("gold ok" if not bad else f"{bad} problem(s)")
sys.exit(1 if bad else 0)
