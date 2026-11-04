"""Thin wrapper around the class proxy. Key and base URL are read from the environment by OpenAI().

Deterministic (temperature 0, non-streaming, no tools) chat calls and all embeddings are cached on disk so
evaluation reruns are fast and reproducible. Set LLM_CACHE=0 to bypass the chat cache.
"""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from types import SimpleNamespace

from openai import OpenAI

from . import config


@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI()


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _fake_completion(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))])


def chat(messages: list[dict], temperature: float = 0.0, **kw):
    cacheable = os.getenv("LLM_CACHE", "1") != "0" and temperature == 0 and not kw.get("stream") and not kw.get("tools")
    path = config.CACHE_DIR / "chat" / f"{_key(config.CHAT_MODEL, messages, kw)}.json"
    if cacheable and path.exists():
        return _fake_completion(json.loads(path.read_text())["content"])
    resp = client().chat.completions.create(model=config.CHAT_MODEL, messages=messages, temperature=temperature, **kw)
    if cacheable:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"content": resp.choices[0].message.content}))
    return resp


def _embed_batch(texts: list[str]) -> list[list[float]]:
    resp = client().embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def embed(texts: list[str], batch: int = 16, workers: int = 4) -> list[list[float]]:
    batches = [texts[i:i + batch] for i in range(0, len(texts), batch)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [v for part in pool.map(_embed_batch, batches) for v in part]


def embed_query(text: str) -> list[float]:
    path = config.CACHE_DIR / "query" / f"{_key(config.EMBED_MODEL, text)}.json"
    if path.exists():
        return json.loads(path.read_text())
    vec = embed([text])[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vec))
    return vec
