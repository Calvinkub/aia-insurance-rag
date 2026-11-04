"""Central configuration. Secrets come from the environment only (OPENAI_API_KEY / OPENAI_BASE_URL)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PAGES_PATH = ROOT / "data" / "pages.jsonl"
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"
CACHE_DIR = ROOT / "data" / "cache"

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemma-4-E4B-it")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")

# Retrieval defaults (tuned in eval/run_eval.py, see README results table).
CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "180"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "40"))
TOP_K = int(os.getenv("TOP_K", "5"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.0"))
