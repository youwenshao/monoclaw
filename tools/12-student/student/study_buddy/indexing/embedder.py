"""Sentence-transformer embedding model loader and encoder."""

from __future__ import annotations

from typing import Any

_model: Any = None
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def get_embedding_model() -> Any:
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [vec.tolist() for vec in embeddings]
