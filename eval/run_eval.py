"""Reproducible evaluation.

  python eval/run_eval.py retrieval              # mode x chunk-size sweep + min_score gate sweep (page-level gold)
  python eval/run_eval.py answers [--chunk W --overlap O --min-score S]   # end-to-end vs baselines

Gold: eval/gold.jsonl (28 answerable + 6 unanswerable). Retrieval hit = a top-k chunk from the gold product on a gold page.
Answer correct = every gold keyword appears in the answer as a whole token (case-insensitive). Everything runs at temperature 0.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if os.getenv("ENV_FILE"):
    from dotenv import load_dotenv
    load_dotenv(os.environ["ENV_FILE"])

from aia_rag import config, llm, rag  # noqa: E402
from aia_rag.ingest import build_chunks, read_jsonl  # noqa: E402
from aia_rag.retrieve import Retriever  # noqa: E402

RESULTS = ROOT / "eval" / "results"
GOLD = read_jsonl(ROOT / "eval" / "gold.jsonl")
ANSWERABLE = [g for g in GOLD if g["answerable"]]
UNANSWERABLE = [g for g in GOLD if not g["answerable"]]
PAGES = read_jsonl(config.PAGES_PATH)


def page_hit(hit, g) -> bool:
    return hit.chunk["product"] == g["product"] and hit.chunk["page"] in g["pages"]


def retrieval_metrics(r: Retriever, k: int = 5) -> dict:
    ranks = []
    for g in ANSWERABLE:
        hits = r.search(g["question"], k=k, min_score=0.0)
        ranks.append(next((h.rank for h in hits if page_hit(h, g)), None))
    n = len(ranks)
    at = lambda m: sum(1 for x in ranks if x is not None and x <= m) / n
    return {"hit@1": at(1), "hit@3": at(3), "hit@5": at(5),
            "mrr": sum(1 / x for x in ranks if x) / n, "missed": [g["id"] for g, x in zip(ANSWERABLE, ranks) if x is None]}


def cmd_retrieval(_args) -> None:
    RESULTS.mkdir(exist_ok=True)
    out = {"mode_x_chunk": [], "gate": []}
    sizes = [(80, 20), (180, 40), (350, 60)]
    print(f"{'chunk':>10} {'mode':>7} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6}")
    for w, o in sizes:
        chunks = build_chunks(PAGES, w, o)
        for mode in ["bm25", "dense", "hybrid"]:
            m = retrieval_metrics(Retriever(chunks, mode))
            out["mode_x_chunk"].append({"words": w, "overlap": o, "n_chunks": len(chunks), "mode": mode, **m})
            print(f"{w:>4}/{o:<4}({len(chunks):>3}) {mode:>7} {m['hit@1']:6.2f} {m['hit@3']:6.2f} {m['hit@5']:6.2f} {m['mrr']:6.3f}")
    # min_score gate: best dense cosine per query; answerable should pass, unanswerable should be blocked
    r = Retriever(build_chunks(PAGES, args_chunk(_args), args_overlap(_args)), "hybrid")
    top = {g["id"]: float(r._dense(g["question"]).max()) for g in GOLD}
    print("\nmin_score gate (hybrid, best dense cosine per query)")
    print(f"{'thr':>5} {'answerable kept':>16} {'unanswerable blocked':>21} {'balanced':>9}")
    for thr in np.arange(0.30, 0.86, 0.05):
        kept = np.mean([top[g["id"]] >= thr for g in ANSWERABLE])
        blocked = np.mean([top[g["id"]] < thr for g in UNANSWERABLE])
        out["gate"].append({"min_score": round(float(thr), 2), "answerable_kept": float(kept), "unanswerable_blocked": float(blocked)})
        print(f"{thr:5.2f} {kept:16.2f} {blocked:21.2f} {(kept + blocked) / 2:9.2f}")
    out["top_scores"] = top
    (RESULTS / "retrieval.json").write_text(json.dumps(out, indent=1))


args_chunk = lambda a: a.chunk
args_overlap = lambda a: a.overlap

CLOSED_BOOK = ("You answer questions about AIA Thailand insurance products from your own knowledge only. "
               "If you are not certain of the exact figure or fact, set answerable=false. "
               'Reply with JSON only: {"answerable": bool, "answer": str, "citations": []}')


CLOSED_BOOK_GUESS = ("You answer questions about AIA Thailand insurance products from your own knowledge only. "
                     "Always give your best specific answer, even if unsure; always set answerable=true. "
                     'Reply with JSON only: {"answerable": true, "answer": str, "citations": []}')


def run_closed_book(question: str, prompt: str = CLOSED_BOOK):
    raw = llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": question}],
                   temperature=0, max_tokens=500).choices[0].message.content or ""
    try:
        a = rag.parse_model_json(raw)
        return {"answerable": a.answerable, "answer": a.answer, "citations": []}
    except Exception:
        return {"answerable": False, "answer": "", "citations": [], "invalid": True}


def run_rag(question: str, retriever: Retriever, min_score: float):
    r = rag.answer_question(question, retriever, min_score=min_score)
    return {"answerable": r.answerable, "answer": r.answer, "abstain_reason": r.abstain_reason,
            "citations": [c.model_dump() for c in r.citations]}


norm = lambda s: " ".join(s.lower().split())


def has_keyword(answer: str, kw: str) -> bool:
    """Whole-token match, so 'no' does not match 'not' and '40' does not match '140%'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(norm(kw))}(?![a-z0-9])", norm(answer)) is not None


def score(g: dict, res: dict) -> dict:
    if g["answerable"]:
        correct = res["answerable"] and all(has_keyword(res["answer"], k) for k in g["keywords"])
        cites = res.get("citations", [])
        return {"correct": correct, "false_abstain": not res["answerable"],
                "cites_gold": any(c["verified"] and c["product"] == g["product"] and c["page"] in g["pages"] for c in cites),
                "n_cites": len(cites), "n_verified": sum(c["verified"] for c in cites)}
    return {"abstained": not res["answerable"]}


def cmd_answers(args) -> None:
    RESULTS.mkdir(exist_ok=True)
    chunks = build_chunks(PAGES, args.chunk, args.overlap)
    bm, hy = Retriever(chunks, "bm25"), Retriever(chunks, "hybrid")
    configs = {
        "closed_book, may abstain": lambda q: run_closed_book(q),
        "closed_book, forced guess": lambda q: run_closed_book(q, CLOSED_BOOK_GUESS),
        "bm25 RAG, no floor": lambda q: run_rag(q, bm, 0.0),
        "hybrid RAG, no floor": lambda q: run_rag(q, hy, 0.0),
        f"hybrid RAG, min_score={args.min_score}": lambda q: run_rag(q, hy, args.min_score),
    }
    summary = {}
    for name, fn in configs.items():
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda g: fn(g["question"]), GOLD))
        scored = [score(g, r) for g, r in zip(GOLD, results)]
        a = [s for g, s in zip(GOLD, scored) if g["answerable"]]
        u = [s for g, s in zip(GOLD, scored) if not g["answerable"]]
        n_c = sum(s["n_cites"] for s in a)
        summary[name] = {
            "accuracy": sum(s["correct"] for s in a) / len(a),
            "false_abstain_rate": sum(s["false_abstain"] for s in a) / len(a),
            "abstain_on_unanswerable": sum(s["abstained"] for s in u) / len(u),
            "cites_gold_page": sum(s["cites_gold"] for s in a) / len(a),
            "citation_verified_rate": (sum(s["n_verified"] for s in a) / n_c) if n_c else None,
        }
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        (RESULTS / f"answers_{slug}.jsonl").write_text(
            "\n".join(json.dumps({"id": g["id"], "question": g["question"], "result": r, "score": s}, ensure_ascii=False)
                      for g, r, s in zip(GOLD, results, scored)))
        print(f"{name:40s} " + "  ".join(f"{k}={v:.2f}" if v is not None else f"{k}=n/a" for k, v in summary[name].items()))
    summary["_meta"] = {"chunk_words": args.chunk, "overlap": args.overlap, "k": config.TOP_K, "chat_model": config.CHAT_MODEL,
                        "embed_model": config.EMBED_MODEL, "n_answerable": len(ANSWERABLE), "n_unanswerable": len(UNANSWERABLE)}
    (RESULTS / "answers_summary.json").write_text(json.dumps(summary, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["retrieval", "answers"])
    ap.add_argument("--chunk", type=int, default=config.CHUNK_WORDS)
    ap.add_argument("--overlap", type=int, default=config.CHUNK_OVERLAP)
    ap.add_argument("--min-score", type=float, default=config.MIN_SCORE)
    args = ap.parse_args()
    {"retrieval": cmd_retrieval, "answers": cmd_answers}[args.cmd](args)


if __name__ == "__main__":
    main()
