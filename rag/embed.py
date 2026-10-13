"""Local embedders. No API keys, no network after the first model download.

RAG_EMBEDDER=e5 (default): intfloat/multilingual-e5-small via sentence-transformers on CPU, 384 dims.
RAG_EMBEDDER=hash: deterministic character-n-gram hashing, 384 dims. For tests only (no model download).
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import numpy as np

from db.models import EMBED_DIM

E5_MODEL = "intfloat/multilingual-e5-small"


class HashEmbedder:
    name = "hash-ngram-384"

    def _one(self, text: str) -> np.ndarray:
        v = np.zeros(EMBED_DIM, dtype=np.float32)
        t = " ".join(text.lower().split())
        for n in (2, 3):
            for i in range(max(0, len(t) - n + 1)):
                h = int.from_bytes(hashlib.blake2b(t[i:i + n].encode(), digest_size=4).digest(), "little")
                v[h % EMBED_DIM] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._one(t) for t in texts]) if texts else np.zeros((0, EMBED_DIM), np.float32)

    def query(self, text: str) -> np.ndarray:
        return self._one(text)


class E5Embedder:
    name = E5_MODEL

    @property
    def model(self):
        return _load_e5()

    def passages(self, texts: list[str]) -> np.ndarray:
        # e5 expects "passage: " / "query: " prefixes
        return self.model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True,
                                 batch_size=32, show_progress_bar=False)

    def query(self, text: str) -> np.ndarray:
        return self.model.encode([f"query: {text}"], normalize_embeddings=True, show_progress_bar=False)[0]


@lru_cache(maxsize=1)
def _load_e5():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(E5_MODEL, device="cpu")


def get_embedder(kind: str | None = None):
    kind = (kind or os.environ.get("RAG_EMBEDDER", "e5")).lower()
    if kind == "hash":
        return HashEmbedder()
    if kind == "e5":
        return E5Embedder()
    raise ValueError(f"unknown RAG_EMBEDDER {kind!r} (e5 | hash)")


def warm(kind: str | None = None) -> str:
    """Load (and on first use download) the embedder and run one query, so the first /chat is not the one paying
    the ~9 s model load. Called by the API lifespan, `make warm` and the Docker build."""
    emb = get_embedder(kind)
    emb.query("워밍업")
    return emb.name


if __name__ == "__main__":
    import argparse
    import time
    ap = argparse.ArgumentParser(description="RAG embedder utilities")
    ap.add_argument("--warm", action="store_true", help="load the embedder once (downloads the model if missing)")
    a = ap.parse_args()
    if a.warm:
        t = time.time()
        print(f"embedder {warm()} ready in {time.time() - t:.1f}s")
