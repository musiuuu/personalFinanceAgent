"""Embedding + retrieval over unstructured document text (invoices, terms).

Uses sentence-transformers (all-MiniLM-L6-v2, local, free) when installed.
Falls back to a deterministic hashing bag-of-words embedding otherwise so the
feature degrades gracefully instead of breaking the app. Vectors are stored
as float32 bytes on DocChunk; search is brute-force cosine, which is plenty
for a single-user corpus.
"""
import hashlib
import math
import re

import numpy as np
from sqlmodel import Session, select

from ..models import DocChunk

_DIM = 384
_model = None
_model_unavailable = False


def _sentence_transformer():
    global _model, _model_unavailable
    if _model is None and not _model_unavailable:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            _model_unavailable = True
    return _model


def _hashing_embed(text: str) -> np.ndarray:
    """Deterministic fallback: hashed bag-of-words with sublinear tf."""
    vec = np.zeros(_DIM, dtype=np.float32)
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        h = int.from_bytes(hashlib.md5(token.encode()).digest()[:8], "little")
        vec[h % _DIM] += 1.0
    nonzero = vec > 0
    vec[nonzero] = 1.0 + np.log(vec[nonzero])
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def embed(text: str) -> np.ndarray:
    model = _sentence_transformer()
    if model is not None:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype=np.float32)
    return _hashing_embed(text)


def chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        # Prefer to break on sentence-ish boundaries.
        if end < len(text):
            cut = text.rfind(". ", start + max_chars // 2, end)
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def index_document(session: Session, doc_id: int, text: str) -> int:
    chunks = chunk_text(text)
    for c in chunks:
        session.add(
            DocChunk(source_doc_id=doc_id, text=c, embedding=embed(c).tobytes())
        )
    return len(chunks)


def search(session: Session, query: str, top_k: int = 4) -> list[tuple[float, DocChunk]]:
    q = embed(query)
    scored: list[tuple[float, DocChunk]] = []
    for chunk in session.exec(select(DocChunk)).all():
        v = np.frombuffer(chunk.embedding, dtype=np.float32)
        if v.shape != q.shape:
            continue  # indexed under a different embedding backend
        denom = float(np.linalg.norm(q) * np.linalg.norm(v))
        score = float(np.dot(q, v) / denom) if denom else 0.0
        if not math.isnan(score):
            scored.append((score, chunk))
    scored.sort(key=lambda s: s[0], reverse=True)
    return scored[:top_k]
