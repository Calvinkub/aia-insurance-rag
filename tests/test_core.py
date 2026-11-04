"""Offline tests: no network, no proxy."""
import pytest

from aia_rag.ingest import build_chunks, is_english
from aia_rag.rag import parse_model_json, resolve_citations
from aia_rag.retrieve import Hit, tokenize
from aia_rag.schemas import Citation, ModelAnswer
from aia_rag.tools import ToolBox, safe_eval


class StubRetriever:
    chunks = [{"product": "AIA X", "page": 1, "text": "hello"}]

    def search(self, *a, **k):
        return []


def test_tokenize_drops_stopwords_keeps_numbers():
    assert tokenize("What is the waiting period of 1,000 Baht?") == ["waiting", "period", "1,000", "baht"]


def test_chunking_overlap_and_metadata():
    page = {"doc": "d.pdf", "product": "P", "page": 3, "text": " ".join(f"w{i}" for i in range(100))}
    chunks = build_chunks([page], words=40, overlap=10)
    assert [c["page"] for c in chunks] == [3] * len(chunks) and len(chunks) == 3
    assert chunks[1]["text"].split()[0] == "w30"  # step = 40 - 10
    assert [c["id"] for c in chunks] == [0, 1, 2]


def test_is_english_rejects_thai():
    assert is_english("Issue age 11 to 75 years old")
    assert not is_english("เอไอเอ สะสมทรัพย 15/25 ไมมีเงินปนผล")


@pytest.mark.parametrize("raw", ['{"answerable": true, "answer": "60 days", "citations": []}',
                                 '```json\n{"answerable": true, "answer": "60 days"}\n```',
                                 'Sure! {"answerable": false, "answer": "n/a"} done'])
def test_parse_model_json_accepts_fenced_and_wrapped(raw):
    assert isinstance(parse_model_json(raw), ModelAnswer)


@pytest.mark.parametrize("raw", ["no json here", '{"answerable": "maybe"}', '{"answer": "missing flag"}'])
def test_parse_model_json_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_model_json(raw)


def test_citations_drop_invented_sources_and_verify_quotes():
    hits = [Hit({"product": "AIA CI Care", "page": 7, "text": 'The "Waiting Period" of AIA CI Care is 60 days.'}, 0.9, 1)]
    ans = ModelAnswer(answerable=True, answer="60 days", citations=[
        Citation(source="S1", quote="Waiting Period of AIA CI Care is 60 days"),
        Citation(source="S1", quote="this sentence is made up"),
        Citation(source="S9", quote="invented source id")])
    out = resolve_citations(ans, hits)
    assert [(c.page, c.verified) for c in out] == [(7, True), (7, False)]


@pytest.mark.parametrize("expr,val", [("2+3*4", 14), ("1,000,000*1.4", 1400000), ("-(2**3)", -8), ("10 % 4", 2)])
def test_safe_eval_arithmetic(expr, val):
    assert safe_eval(expr) == pytest.approx(val)


@pytest.mark.parametrize("expr", ["__import__('os').system('id')", "open('/etc/passwd')", "2**9999", "a+1", "(1).real"])
def test_safe_eval_rejects_everything_else(expr):
    with pytest.raises(ValueError):
        safe_eval(expr)


def test_toolbox_allowlist_and_validation():
    tb = ToolBox(StubRetriever())
    assert tb.call("shell", {"cmd": "ls"}).startswith("ERROR: unknown tool")
    assert tb.call("calculate", {}).startswith("ERROR")  # missing argument
    assert tb.call("calculate", {"expression": "1/0"}).startswith("ERROR")
    assert tb.call("calculate", {"expression": "2*21"}) == "42.0"
    assert tb.call("list_products", {}) == "AIA X"
    assert tb.call("search_brochures", {"query": "x"}).startswith("ERROR")  # too short -> validation error


# ---- chunking experiments (aia_rag/chunking.py) ----
from aia_rag.chunking import build_parent_child, chunk_units, strip_boilerplate, to_units  # noqa: E402
from aia_rag.retrieve import Retriever  # noqa: E402


def test_to_units_separates_tables_and_sentences():
    text = "First sentence here. Second one follows.\n\n|H1|H2|\n|---|---|\n|a|b|\n\nAfter table."
    kinds = [k for k, _ in to_units(text)]
    assert kinds == ["sent", "sent", "table", "sent"]


def test_strip_boilerplate_removes_only_repeated_long_sentences():
    boiler = "The insured is obliged to declare facts in applying for insurance."
    pages = [{"doc": "d", "product": "P", "page": i, "text": f"{boiler} Unique fact number {i} appears here today."} for i in (1, 2, 3)]
    out = strip_boilerplate(pages)
    assert all(boiler not in " ".join(s for _, s in p["units"]) for p in out)
    assert all(f"Unique fact number {p['page']}" in " ".join(s for _, s in p["units"]) for p in out)


def test_table_chunks_repeat_header_row():
    rows = "\n".join(f"|row{i}|" + " ".join(["w"] * 30) + "|" for i in range(8))
    page = {"doc": "d", "product": "P", "page": 1, "units": [("table", "|Head A|Head B|\n|---|---|\n" + rows)]}
    chunks = chunk_units(page, words=60, overlap=0)
    assert len(chunks) > 1 and all(c["text"].startswith("|Head A|Head B|") for c in chunks)


def test_sentence_chunks_do_not_cut_mid_sentence():
    sents = [f"Sentence {i} has exactly seven words in it." for i in range(30)]
    page = {"doc": "d", "product": "P", "page": 1, "units": [("sent", s) for s in sents]}
    assert all(c["text"].endswith("it.") for c in chunk_units(page, words=40, overlap=8))


def test_parent_child_returns_parent_page_deduplicated():
    page = {"doc": "d", "product": "P", "page": 1, "text": " ".join(f"Fact {i} is stated plainly here." for i in range(30))}
    kids = build_parent_child([page], child_words=20, child_overlap=0)
    assert len(kids) > 3 and all(k["parent_text"] == kids[0]["parent_text"] for k in kids)
    merged = Retriever._merge_parents([Hit(k, 1.0, i) for i, k in enumerate(kids[:4])], k=5)
    assert len(merged) == 1 and merged[0].chunk["text"] == kids[0]["parent_text"]
