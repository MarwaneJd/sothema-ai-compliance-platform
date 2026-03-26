import os
import pickle

import faiss
import numpy as np
import structlog

from app.core.exceptions import VectorStoreError

logger = structlog.get_logger()


class FAISSVectorStore:
    """FAISS vector store with IndexFlatIP (cosine similarity via normalized vectors).

    Uses a plain IndexFlatIP (no IndexIDMap wrapper) to avoid SWIG/ARM64 segfaults.
    ID mapping is managed entirely in Python via the metadata pickle.
    """

    def __init__(self, index_path: str, dimensions: int = 3072):
        self.index_path = index_path
        self.dimensions = dimensions
        self.index: faiss.IndexFlatIP | None = None
        # Maps positional index (row in FAISS) → VectorStoreId string
        self._pos_to_vs_id: list[str] = []
        self._vs_id_to_pos: dict[str, int] = {}

    @property
    def size(self) -> int:
        if self.index is None:
            return 0
        return self.index.ntotal

    def load(self) -> None:
        """Load FAISS index and metadata from disk. Creates new if not found."""
        index_file = os.path.join(self.index_path, "faiss.index")
        meta_file = os.path.join(self.index_path, "faiss_meta.pkl")

        if os.path.exists(index_file) and os.path.exists(meta_file):
            try:
                raw_index = faiss.read_index(index_file)
                # Unwrap IndexIDMap if the saved index was wrapped
                if hasattr(raw_index, "index"):
                    self.index = faiss.downcast_index(raw_index.index)
                else:
                    self.index = raw_index

                with open(meta_file, "rb") as f:
                    meta = pickle.load(f)

                # Support both old (id_to_vector_store_id dict) and new (pos list) formats
                if "pos_to_vs_id" in meta:
                    self._pos_to_vs_id = meta["pos_to_vs_id"]
                elif "id_to_vector_store_id" in meta:
                    old_map = meta["id_to_vector_store_id"]
                    max_id = max(old_map.keys()) if old_map else -1
                    self._pos_to_vs_id = [""] * (max_id + 1)
                    for int_id, vs_id in old_map.items():
                        self._pos_to_vs_id[int_id] = vs_id
                else:
                    self._pos_to_vs_id = []

                self._vs_id_to_pos = {
                    vs_id: pos
                    for pos, vs_id in enumerate(self._pos_to_vs_id)
                    if vs_id
                }
                logger.info("FAISS index loaded", size=self.index.ntotal)
            except Exception as e:
                logger.error("Failed to load FAISS index, creating new", error=str(e))
                self._create_new_index()
        else:
            logger.info("No existing FAISS index found, creating new")
            self._create_new_index()

    def save(self) -> None:
        """Persist FAISS index and metadata to disk."""
        if self.index is None:
            return

        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "faiss.index")
        meta_file = os.path.join(self.index_path, "faiss_meta.pkl")

        try:
            faiss.write_index(self.index, index_file)
            meta = {
                "pos_to_vs_id": self._pos_to_vs_id,
                "next_id": len(self._pos_to_vs_id),
                # Keep old keys for backwards compat if needed
                "id_to_vector_store_id": {
                    i: vs_id
                    for i, vs_id in enumerate(self._pos_to_vs_id)
                    if vs_id
                },
                "vector_store_id_to_id": self._vs_id_to_pos,
            }
            with open(meta_file, "wb") as f:
                pickle.dump(meta, f)
            logger.info("FAISS index saved", size=self.index.ntotal)
        except Exception as e:
            raise VectorStoreError(f"Failed to save FAISS index: {e}") from e

    def add_vectors(
        self, vectors: list[np.ndarray], vector_store_ids: list[str]
    ) -> None:
        """Add normalized vectors to the index with associated VectorStoreId strings."""
        if self.index is None:
            self._create_new_index()

        if len(vectors) != len(vector_store_ids):
            raise VectorStoreError("Vectors and IDs must have the same length")

        if not vectors:
            return

        vectors_array = np.stack(vectors).astype(np.float32)

        # Track positional mapping
        for vs_id in vector_store_ids:
            pos = len(self._pos_to_vs_id)
            self._pos_to_vs_id.append(vs_id)
            self._vs_id_to_pos[vs_id] = pos

        self.index.add(vectors_array)  # type: ignore[union-attr]
        logger.info("Vectors added to FAISS", count=len(vectors))

    def search(
        self, query_vector: np.ndarray, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search for nearest vectors. Returns list of (VectorStoreId, score)."""
        if self.index is None or self.index.ntotal == 0:
            return []

        query = query_vector.reshape(1, -1).astype(np.float32)
        actual_k = min(top_k, self.index.ntotal)

        scores, ids = self.index.search(query, actual_k)

        results = []
        for score, pos in zip(scores[0], ids[0]):
            if pos == -1 or pos >= len(self._pos_to_vs_id):
                continue
            vs_id = self._pos_to_vs_id[int(pos)]
            if vs_id:
                results.append((vs_id, float(score)))

        return results

    def remove_vectors(self, vector_store_ids: list[str]) -> None:
        """Remove vectors by VectorStoreId. Rebuilds the index without removed vectors."""
        if self.index is None or not vector_store_ids:
            return

        remove_set = set(vector_store_ids)
        # Reconstruct all vectors from the current index
        n = self.index.ntotal
        if n == 0:
            return

        all_vectors = faiss.rev_swig_ptr(
            self.index.get_xb(), n * self.dimensions
        ).reshape(n, self.dimensions).copy()

        # Filter out removed vectors
        keep_indices = [
            i for i, vs_id in enumerate(self._pos_to_vs_id)
            if vs_id and vs_id not in remove_set
        ]

        # Rebuild
        self._create_new_index()
        if keep_indices:
            kept_vectors = all_vectors[keep_indices]
            kept_ids = [self._pos_to_vs_id[i] for i in keep_indices]
            # Reset mappings before re-adding
            self._pos_to_vs_id = []
            self._vs_id_to_pos = {}
            self.add_vectors(
                [kept_vectors[i] for i in range(len(kept_vectors))],
                kept_ids,
            )
        else:
            self._pos_to_vs_id = []
            self._vs_id_to_pos = {}

        logger.info("Vectors removed from FAISS", count=len(remove_set))

    def _create_new_index(self) -> None:
        self.index = faiss.IndexFlatIP(self.dimensions)
        self._pos_to_vs_id = []
        self._vs_id_to_pos = {}
