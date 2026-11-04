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
