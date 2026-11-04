"""FastAPI backend: POST /ask, GET /ask/stream (SSE), GET /agent/stream (SSE), GET / (tiny UI)."""
import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from . import config
from .agent import run_agent
from .ingest import read_jsonl
from .rag import answer_question, stream_answer
from .retrieve import Retriever
from .schemas import AskRequest, RagResponse
from .tools import ToolBox

app = FastAPI(title="AIA Brochure Q&A")
STATIC = Path(__file__).resolve().parent.parent / "static"


@lru_cache(maxsize=1)
def retriever() -> Retriever:
    if not config.CHUNKS_PATH.exists():
        raise HTTPException(503, "Run `python -m aia_rag.ingest` first.")
    return Retriever(read_jsonl(config.CHUNKS_PATH), "hybrid")


def sse(events):
    for e in events:
        yield f"event: {e['event']}\ndata: {json.dumps(e['data'], ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok", "chat_model": config.CHAT_MODEL, "embed_model": config.EMBED_MODEL}


@app.post("/ask", response_model=RagResponse)
def ask(req: AskRequest):
    return answer_question(req.question, retriever(), min_score=config.MIN_SCORE)


@app.get("/ask/stream")
def ask_stream(q: str = Query(min_length=3, max_length=500)):
    return StreamingResponse(sse(stream_answer(q, retriever(), min_score=config.MIN_SCORE)),
                             media_type="text/event-stream")


@app.get("/agent/stream")
def agent_stream(q: str = Query(min_length=3, max_length=500)):
    return StreamingResponse(sse(run_agent(q, ToolBox(retriever()))), media_type="text/event-stream")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
