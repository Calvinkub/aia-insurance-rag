"""Retrieval: BM25, dense (bge-m3 via proxy), and hybrid (reciprocal-rank fusion) with a min_score floor.

min_score semantics (so it is comparable across modes):
  dense / hybrid : cosine similarity of the chunk to the query must be >= min_score
  bm25           : BM25 score divided by the best BM25 score for the query must be >= min_score
"""
import hashlib
import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from . import config, llm

_TOKEN = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")
_STOP = frozenset("a an and are as at be by for from has have how in is it its of on or that the this to what which with will can do does i my me".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass
class Hit:
    chunk: dict
    score: float
    rank: int


def _embed_cached(texts: list[str]) -> np.ndarray:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(("\n".join(texts) + config.EMBED_MODEL).encode()).hexdigest()[:16]
    path = config.CACHE_DIR / f"emb_{key}.npy"
    if path.exists():
        return np.load(path)
    arr = np.asarray(llm.embed(texts), dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
    np.save(path, arr)
    return arr


class Retriever:
    def __init__(self, chunks: list[dict], mode: str = "hybrid"):
        if mode not in {"bm25", "dense", "hybrid"}:
            raise ValueError(f"unknown mode {mode!r}")
        self.chunks, self.mode = chunks, mode
        # Product name is prepended to every chunk so "Health Happy ..." queries can match on it.
        texts = [f"{c['product']}. {c['text']}" for c in chunks]
        self.bm25 = BM25Okapi([tokenize(t) for t in texts]) if mode in {"bm25", "hybrid"} else None
        self.emb = _embed_cached(texts) if mode in {"dense", "hybrid"} else None

    def _dense(self, query: str) -> np.ndarray:
        q = np.asarray(llm.embed_query(query), dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-9
        return self.emb @ q

    def search(self, query: str, k: int = config.TOP_K, min_score: float = config.MIN_SCORE,
               product: str | None = None) -> list[Hit]:
        n = len(self.chunks)
        allowed = np.array([product is None or product.lower() in c["product"].lower() for c in self.chunks])
        bm = dn = None
        if self.bm25 is not None:
            bm = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
        if self.emb is not None:
            dn = self._dense(query)

        if self.mode == "bm25":
            rank_score, floor_score = bm, bm / (bm.max() + 1e-9)
        elif self.mode == "dense":
            rank_score, floor_score = dn, dn
        else:  # reciprocal-rank fusion, constant 60
            rrf = np.zeros(n, dtype=np.float32)
            for s in (bm, dn):
                order = np.argsort(-s)
                rrf[order] += 1.0 / (60 + np.arange(1, n + 1))
            rank_score, floor_score = rrf, dn

        rank_score = np.where(allowed, rank_score, -np.inf)
        hits = []
        for idx in np.argsort(-rank_score):
            if not np.isfinite(rank_score[idx]) or len(hits) >= k:
                break
            if floor_score[idx] < min_score:
                continue
            hits.append(Hit(self.chunks[idx], float(floor_score[idx]), len(hits) + 1))
        return hits
