"""Chunking experiments. Variants (E0 is the shipped baseline in ingest.py):

  E1  pypdf text -> drop boilerplate sentences repeated on >=3 pages of a doc -> sentence-aware packing
  E2  PyMuPDF4LLM markdown (tables preserved) -> same boilerplate drop -> sentence packing + tables split by
      row groups with the header row repeated in every chunk
  E4  parent-child (small-to-big): index ~60-word child chunks from the E1 pipeline, but return the whole
      (boilerplate-stripped) page as the context passage; children of the same page are merged
  E3  E2 + contextual prefix: one gemma call per chunk writes a short situating blurb that is indexed with the
      chunk (Anthropic "contextual retrieval"); the blurb is stored in chunk["context"], text stays untouched
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import config, llm
from .ingest import extract_pages, is_english, product_name, write_jsonl, read_jsonl

_SENT = re.compile(r"(?<=[.!?:])\s+(?=[A-Z0-9•\-–“\"(])")
_norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def clean_md(text: str) -> str:
    text = text.replace("<br>", " ").replace("**", "").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_pages_md(raw_dir: Path = config.RAW_DIR) -> list[dict]:
    import pymupdf
    import pymupdf4llm
    pages = []
    for pdf in sorted(raw_dir.glob("*.pdf")):
        doc = pymupdf.open(str(pdf))
        parts = pymupdf4llm.to_markdown(doc, page_chunks=True, header=False, footer=False, show_progress=False)
        for i, part in enumerate(parts, start=1):
            text = clean_md(part["text"])
            if text and is_english(re.sub(r"[|\-:]", " ", text)):
                pages.append({"doc": pdf.name, "product": product_name(pdf.name), "page": i, "text": text})
    return pages


def to_units(text: str) -> list[tuple[str, str]]:
    """Split a page into ('table', block) and ('sent', sentence) units, in order."""
    units, para, table = [], [], []

    def flush_para():
        if para:
            units.extend(("sent", s.strip()) for s in _SENT.split(" ".join(para)) if s.strip())
            para.clear()

    def flush_table():
        if table:
            units.append(("table", "\n".join(table)))
            table.clear()

    for line in text.splitlines():
        if line.strip().startswith("|"):
            flush_para(); table.append(line.strip())
        elif not line.strip():
            flush_para(); flush_table()
        else:
            flush_table(); para.append(line.strip())
    flush_para(); flush_table()
    return units


def strip_boilerplate(pages: list[dict], min_pages: int = 3, min_words: int = 6) -> list[dict]:
    """Remove sentences (>= min_words) that occur on >= min_pages distinct pages of the same document."""
    seen: dict[str, Counter] = defaultdict(Counter)
    page_units = []
    for p in pages:
        us = to_units(p["text"])
        page_units.append(us)
        for kind, s in set(us):
            if kind == "sent" and len(s.split()) >= min_words:
                seen[p["doc"]][_norm(s)] += 1
    out = []
    for p, us in zip(pages, page_units):
        keep = [(k, s) for k, s in us if not (k == "sent" and seen[p["doc"]][_norm(s)] >= min_pages and len(s.split()) >= min_words)]
        out.append({**p, "units": keep})
    return out


def chunk_units(page: dict, words: int, overlap: int) -> list[dict]:
    chunks, buf = [], []

    def emit(text: str):
        if text.strip():
            chunks.append({"doc": page["doc"], "product": page["product"], "page": page["page"], "text": text.strip()})

    def flush():
        nonlocal buf
        emit(" ".join(buf)); buf = []

    for kind, s in page["units"]:
        if kind == "table":
            flush()
            rows = s.split("\n")
            head, body = rows[:2], rows[2:]
            if not body:
                emit(s); continue
            cur, n = [], 0
            for row in body:
                rw = len(row.split())
                if cur and n + rw > words:
                    emit("\n".join(head + cur)); cur, n = [], 0
                cur.append(row); n += rw
            emit("\n".join(head + cur))
        else:
            if buf and sum(len(x.split()) for x in buf) + len(s.split()) > words:
                tail = buf[-1] if len(buf[-1].split()) <= overlap else None
                flush()
                if tail:
                    buf = [tail]
            buf.append(s)
    flush()
    # merge a tiny tail chunk into its predecessor (same page)
    if len(chunks) > 1 and len(chunks[-1]["text"].split()) < 40 and "\n|" not in chunks[-1]["text"]:
        last = chunks.pop(); chunks[-1]["text"] += " " + last["text"]
    return chunks


def build_variant_chunks(pages: list[dict], words: int = config.CHUNK_WORDS, overlap: int = config.CHUNK_OVERLAP) -> list[dict]:
    chunks = []
    for p in strip_boilerplate(pages):
        for c in chunk_units(p, words, overlap):
            c["id"] = len(chunks)
            chunks.append(c)
    return chunks


CONTEXT_PROMPT = (
    "Here is one page from the AIA Thailand brochure for the product \"{product}\":\n<page>\n{page}\n</page>\n\n"
    "Here is a chunk from that page:\n<chunk>\n{chunk}\n</chunk>\n\n"
    "Write ONE short sentence (max 35 words) that situates this chunk within the brochure to improve search retrieval: "
    "name the product and say which topic or section the chunk belongs to (e.g. waiting period, issue age, fees, benefits, "
    "tax, exclusions). Use only facts from the page. Reply with the sentence only."
)


def add_context(chunks: list[dict], pages: list[dict], workers: int = 4) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    page_text = {(p["doc"], p["page"]): p["text"] for p in pages}

    def one(c):
        prompt = CONTEXT_PROMPT.format(product=c["product"], page=page_text[(c["doc"], c["page"])][:6000], chunk=c["text"][:2500])
        out = llm.chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=90).choices[0].message.content or ""
        return " ".join(out.split())[:300]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        ctx = list(pool.map(one, chunks))
    return [{**c, "context": x} for c, x in zip(chunks, ctx)]


def build_parent_child(pages: list[dict], child_words: int = 60, child_overlap: int = 15) -> list[dict]:
    children = []
    for p in strip_boilerplate(pages):
        parent = " ".join(t for _, t in p["units"])
        for c in chunk_units(p, child_words, child_overlap):
            c["parent_text"], c["id"] = parent, len(children)
            children.append(c)
    return children


def build_variant(name: str, words: int = config.CHUNK_WORDS, overlap: int = config.CHUNK_OVERLAP) -> list[dict]:
    if name == "E0":
        from .ingest import build_chunks
        return build_chunks(read_jsonl(config.PAGES_PATH), words, overlap)
    if name == "E1":
        return build_variant_chunks(read_jsonl(config.PAGES_PATH), words, overlap)
    if name == "E4":
        return build_parent_child(read_jsonl(config.PAGES_PATH))
    md_path = config.ROOT / "data" / "pages_md.jsonl"
    if not md_path.exists():
        write_jsonl(md_path, extract_pages_md())
    md_pages = read_jsonl(md_path)
    base = build_variant_chunks(md_pages, words, overlap)
    if name == "E2":
        return base
    if name == "E3":
        return add_context(base, md_pages)
    raise ValueError(name)
