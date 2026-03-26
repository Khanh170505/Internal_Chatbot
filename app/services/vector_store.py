import json
import threading
from pathlib import Path
from typing import Callable

import numpy as np

from app.core.config import get_settings

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


FilterFn = Callable[[dict], bool]


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._dir = Path(settings.vectorstore_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._vectors_path = self._dir / "vectors.npy"
        self._meta_path = self._dir / "metadata.json"

        self._lock = threading.Lock()
        self._vectors: np.ndarray = np.zeros((0, 768), dtype=np.float32)
        self._metadata: list[dict] = []
        self._index = None
        self._load()

    def _load(self) -> None:
        if self._vectors_path.exists() and self._meta_path.exists():
            self._vectors = np.load(self._vectors_path)
            self._metadata = json.loads(self._meta_path.read_text(encoding="utf-8"))
        self._rebuild_index()

    def _persist(self) -> None:
        np.save(self._vectors_path, self._vectors)
        self._meta_path.write_text(json.dumps(self._metadata, ensure_ascii=True), encoding="utf-8")

    def _rebuild_index(self) -> None:
        if faiss is None or len(self._vectors) == 0:
            self._index = None
            return
        dim = self._vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(self._vectors)
        self._index = index

    def upsert(self, vectors: np.ndarray, metadata: list[dict]) -> None:
        with self._lock:
            if len(vectors) == 0:
                return
            if self._vectors.size == 0:
                self._vectors = vectors.astype(np.float32)
            else:
                self._vectors = np.vstack([self._vectors, vectors.astype(np.float32)])
            self._metadata.extend(metadata)
            self._rebuild_index()
            self._persist()

    def search(self, query_vec: np.ndarray, top_k: int, filter_fn: FilterFn) -> list[dict]:
        with self._lock:
            if len(self._metadata) == 0:
                return []

            q = query_vec.astype(np.float32)
            if q.ndim == 1:
                q = q.reshape(1, -1)

            if self._index is not None:
                scores, indices = self._index.search(q, min(top_k * 10, len(self._metadata)))
                scored = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx < 0:
                        continue
                    meta = self._metadata[int(idx)]
                    if filter_fn(meta):
                        scored.append({"score": float(score), "metadata": meta})
                    if len(scored) >= top_k:
                        break
                return scored

            similarities = np.dot(self._vectors, q[0])
            order = np.argsort(-similarities)
            results = []
            for idx in order:
                meta = self._metadata[int(idx)]
                if filter_fn(meta):
                    results.append({"score": float(similarities[idx]), "metadata": meta})
                if len(results) >= top_k:
                    break
            return results

    def filtered_metadata(self, filter_fn: FilterFn) -> list[dict]:
        with self._lock:
            return [m for m in self._metadata if filter_fn(m)]


vector_store = VectorStore()
