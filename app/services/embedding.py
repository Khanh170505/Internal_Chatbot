import hashlib
import math

import numpy as np


class LocalEmbeddingService:
    """Lightweight local embedding based on token hashing for MVP stability."""

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            vectors[i] = self._embed_one(text)
        return vectors

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vec

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dim
            sign = -1.0 if int(digest[8:10], 16) % 2 else 1.0
            vec[idx] += sign

        norm = math.sqrt(float(np.dot(vec, vec)))
        if norm > 0:
            vec = vec / norm
        return vec


embedding_service = LocalEmbeddingService()
