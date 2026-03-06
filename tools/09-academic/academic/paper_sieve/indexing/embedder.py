"""Embedding generation using sentence-transformers with lazy singleton loading."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("openclaw.academic.paper_sieve.embedder")

_lock = threading.Lock()
_model_cache: dict[str, Any] = {}

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def get_embedder(model_name: str = DEFAULT_MODEL) -> Any:
    """Return a lazily-loaded SentenceTransformer model (singleton per model_name).

    Thread-safe: concurrent callers will block while the model loads.
    """
    if model_name in _model_cache:
        return _model_cache[model_name]

    with _lock:
        if model_name in _model_cache:
            return _model_cache[model_name]

        logger.info("Loading SentenceTransformer model: %s", model_name)
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        _model_cache[model_name] = model
        logger.info("Model %s loaded successfully", model_name)
        return model


def embed_texts(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 64,
) -> list[list[float]]:
    """Batch-embed a list of texts into dense vectors.

    Returns a list of float vectors, one per input text.
    """
    if not texts:
        return []

    model = get_embedder(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [vec.tolist() for vec in embeddings]


def embed_query(query: str, model_name: str = DEFAULT_MODEL) -> list[float]:
    """Embed a single query string into a dense vector."""
    model = get_embedder(model_name)
    embedding = model.encode(query, convert_to_numpy=True)
    return embedding.tolist()
