from __future__ import annotations

import logging
from typing import Sequence

_log = logging.getLogger(__name__)
_model = None


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """384-d MiniLM vectors when sentence-transformers is installed; else zeros."""
    global _model  # noqa: PLW0603
    if not texts:
        return []
    try:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return _model.encode(list(texts), normalize_embeddings=True).tolist()  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        _log.debug("Embeddings unavailable (%s); returning zero vectors", exc)
        return [[0.0] * 384 for _ in texts]
