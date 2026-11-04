# AIA Brochure Q&A — grounded RAG + agent over AIA Thailand product brochures

Ask questions about AIA Thailand insurance products (waiting periods, issue ages, benefit percentages, fees) and get an
answer **with citations to the brochure page**, or an explicit "the brochures do not say this" instead of a guess.

> Corpus = 15 public English AIA Thailand brochures, dated 2019–2022. This is a course project, **not insurance advice**,
> and the brochures may be out of date.

Course capability families covered: **(1)** structured output with schema validation, **(2)** RAG with citations,
**(3)** retrieval + answer evaluation against baselines, **(4)** agent loop with allow-listed tools, **(6)** FastAPI + SSE streaming.
All LLM calls go through the class proxy (`OpenAI()`, chat model `gemma-4-E4B-it`, embeddings `bge-m3`).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate        # Python 3.10+ (developed on 3.13)
pip install -r requirements.txt
export OPENAI_API_KEY=...  OPENAI_BASE_URL=...            # same variables as the class sandbox; or copy .env.example
python scripts/fetch_corpus.py                            # downloads the 16 brochure PDFs into data/raw/
python -m aia_rag.ingest                                  # PDFs -> data/pages.jsonl + data/chunks.jsonl
uvicorn aia_rag.server:app --reload                       # UI at http://127.0.0.1:8000/
```

The first request embeds all chunks through the proxy (~4 min, then cached in `data/cache/`).

| Endpoint | What it does |
|---|---|
| `POST /ask` `{"question": "..."}` | schema-validated JSON answer with verified citations |
| `GET /ask/stream?q=...` | SSE: `sources` → `token`… → `final` (validated) |
| `GET /agent/stream?q=...` | SSE: each tool call/result, then the final answer |
| `GET /` | minimal UI (RAG or Agent mode) |

```bash
python -m pytest -q tests          # 20 offline tests, no proxy needed
python eval/check_gold.py          # every gold evidence quote must occur on its cited page
ENV_FILE=.env python eval/run_eval.py retrieval    # mode x chunk-size sweep + min_score sweep
ENV_FILE=.env python eval/run_eval.py answers      # end-to-end vs baselines
```

## Design

```
question ─► Retriever (BM25 + bge-m3 dense, reciprocal-rank fusion, optional min_score floor, optional product filter)
        ─► prompt with numbered sources S1..S5 (product + page) ─► gemma-4-E4B-it (temperature 0)
        ─► parse/repair JSON ─► pydantic ModelAnswer ─► resolve citations (drop invented ids, verify quote ⊂ passage)
        ─► RagResponse {answerable, answer, citations[product,page,quote,verified], abstain_reason}
agent: gemma + tools {search_brochures, list_products, calculate}, max 6 steps, then a hard stop
```

Boundary safety: LLM output is parsed and schema-validated (fences stripped, one repair retry, else abstain);
tool names are allow-listed, tool arguments are pydantic-validated, `calculate` is an AST-whitelisted arithmetic evaluator
(no names/calls/attributes, exponent capped); retrieved text and tool results are labelled untrusted in the system prompt;
API key and base URL come only from the environment.

```
aia_rag/  config · ingest · retrieve · llm (proxy + disk cache) · schemas · rag · tools · agent · server
eval/     gold.jsonl (34 questions) · check_gold.py · run_eval.py · results/ (committed outputs)
scripts/  fetch_corpus.py        static/  index.html        tests/  test_core.py        data/pages.jsonl
```

## Evaluation

**Test set** (`eval/gold.jsonl`): 28 answerable questions, each with a verbatim evidence quote, gold product + page and
required keywords; 6 unanswerable questions (topically close but not in the corpus, e.g. Vitality reward tiers).
`eval/check_gold.py` verifies all evidence quotes against the extracted page text. Questions were drafted with AI
assistance from the brochure text; the quote check is what keeps the labels honest.

**Metrics.** Retrieval: page-level hit@k and MRR (a hit is a top-k chunk from the gold product on a gold page).
Answers: *accuracy* = all gold keywords appear in the answer as whole tokens; *false abstain* = answerable question
declined; *abstain on unanswerable*; *cites gold page* = a verified citation points at the gold product+page;
*citation verified* = share of citations whose quote really occurs in the cited passage. Temperature 0 throughout.

### Retrieval (n = 28, k = 5)

| chunk words/overlap | mode | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|---|
| 80/20 | bm25 | 0.75 | 0.93 | 0.93 | 0.839 |
| 80/20 | dense | 0.75 | 0.93 | 0.96 | 0.842 |
| 80/20 | hybrid | 0.79 | 0.93 | 0.93 | 0.857 |
| **180/40** | bm25 *(naive default)* | 0.79 | 0.86 | 0.93 | 0.832 |
| **180/40** | dense | 0.79 | 0.93 | 0.96 | 0.852 |
| **180/40** | **hybrid (chosen)** | **0.82** | **0.93** | **0.96** | **0.882** |
| 350/60 | bm25 | 0.75 | 0.96 | 0.96 | 0.845 |
| 350/60 | dense | 0.68 | 0.86 | 0.96 | 0.787 |
| 350/60 | hybrid | 0.75 | 0.96 | 0.96 | 0.857 |

### End-to-end answers (chunk 180/40, k = 5; 28 answerable + 6 unanswerable)

| system | accuracy | false abstain | abstained on unanswerable | cites gold page | citation verified |
|---|---|---|---|---|---|
| closed-book, may abstain (baseline) | 0.00 | 1.00 | 1.00 | – | – |
| closed-book, forced guess (baseline) | 0.07 | 0.29 | 0.50 | – | – |
| BM25 RAG, no floor | 0.93 | 0.04 | 1.00 | 0.93 | 0.95 |
| **hybrid RAG, no floor (shipped)** | **0.93** | **0.00** | 1.00 | 0.93 | **1.00** |
| hybrid RAG, `min_score=0.65` | 0.89 | 0.04 | 1.00 | 0.89 | 1.00 |

What the numbers say, and do not say:

- **Retrieval is what makes this work.** Closed-book with a forced guess gets 2/28 right and answers 3 of 6 unanswerable
  questions anyway (hallucination). With retrieval: 26/28, no hallucinated answers on the unanswerable set. The
  "may abstain" baseline scores 0 only because the model refuses everything, so the forced-guess baseline is the informative one.
- **Measured improvement over the naive default** (BM25, same chunking): hybrid raises MRR 0.832 → 0.882, hit@1 0.79 → 0.82,
  citation-verified rate 0.95 → 1.00 and removes the single false abstain. **Caveat:** with n = 28 this is one or two
  questions; it is a direction, not a significant result.
- **`min_score` was a negative result.** Sweeping a query-level gate looked free (a threshold of 0.65 kept all 28 answerable
  questions and blocked 4 of 6 unanswerable ones), but applied as a per-chunk floor it removed a correct chunk (cosine 0.62)
  and cost 1 correct answer (0.93 → 0.89). The model already declines all 6 unanswerable questions on its own, so the floor
  buys nothing here. `MIN_SCORE` therefore defaults to 0.
- **Chunk size:** 180 words was best on MRR; 350 hurt dense retrieval. Differences are again within one or two questions.

### Failure cases (hybrid RAG, no floor)

| id | question | what happened | cause |
|---|---|---|---|
| A07 | How many severe-stage critical illnesses does AIA CI Care cover? | Answered "44" (gold: 40). | The gold page is a flattened disease table; `pdf → text` loses the layout, so retrieval never surfaced it. The model then **invented a number from other passages instead of abstaining**. |
| A24 | Which premium payment periods can be chosen for Infinite Wealth Prestige? | Answered with top-up payment *frequency* (monthly, quarterly…). | The gold chunk (p3) ranked 5th; the model answered from a higher-ranked passage using a different sense of "payment period". |
| A17 (only with floor) | Max income tax deduction for Smart Select? | False abstain. | The `min_score=0.65` floor dropped the evidence chunk. |

## Limitations

- **Small, self-built eval, tuned on itself.** Chunk size, retrieval mode and `min_score` were all chosen by looking at the same 34 questions; there is no held-out set, so the shipped numbers are optimistic. Differences of one question are noise.
- **Keyword scoring is a proxy.** It can credit an answer that mentions the right number in the wrong context and can miss correct paraphrases (one gold keyword was a word stem and wrongly failed a correct answer; fixed to a full word). I did not use an LLM judge; a second human read of the answers is still the real check.
- **PDF tables flatten.** Benefit tables (plan amounts, ICU rules) extract as number soup; questions that depend on table structure are the weakest spot (A07).
- **English brochures only.** 3 "EN" files are actually Thai and extract as garbage; they are filtered out (`is_english`), so *AIA Term*, most of *Endowment* and *10/15 Pay Life* are thin or missing. A Thai-capable pipeline is the obvious next step.
- **The agent is not quantitatively evaluated.** It is exercised manually (multi-step comparison, tool-argument rejection tests) but has no gold set; in one manual run it multiplied by hand instead of calling `calculate`.
- **Same model family does everything** (answerer; no independent judge). Embeddings and generation depend on the class proxy.
- **Commit history:** the repo was built in one working session, so the history is a short sequence of logical commits rather than weeks of incremental work.

## Next steps

Table-aware extraction (e.g. layout-preserving text or a table parser) for A07-type questions; a cross-check step that
refuses a numeric answer whose number does not occur in any cited quote (would have caught A07); a larger held-out gold
set written by someone who did not tune the system; Thai support.
