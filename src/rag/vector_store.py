from dataclasses import dataclass
from pathlib import Path
import faiss
import joblib
import numpy as np

from config import config
from src.rag.document_loader import DocumentChunk
from src.rag.embeddings import EmbeddingModel, fit_embedding_model

DEFAULT_INDEX_DIR = config.data_dir / "rag_index"


@dataclass
class PersistedVectorStore:
    index: faiss.Index
    embedding_model: EmbeddingModel
    chunks: list[DocumentChunk]

    def search(self, query: str, top_k: int = 3) -> list[tuple[DocumentChunk, float]]:
        cleaned = (query or "").strip()
        if not cleaned or not self.chunks:
            return []
        q_vec = self.embedding_model.encode([cleaned])
        k = min(max(1, top_k), len(self.chunks))
        scores, indices = self.index.search(q_vec, k)
        results: list[tuple[DocumentChunk, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            results.append((self.chunks[int(idx)], round(float(score), 4)))
        return results


def build_and_persist_vector_store(
    chunks: list[DocumentChunk],
    index_dir: Path | str | None = None,
) -> PersistedVectorStore:
    if not chunks:
        raise ValueError("Cannot build FAISS vector store with zero document chunks.")

    texts = [f"{c.title}. {c.text}" for c in chunks]
    emb_model, vectors = fit_embedding_model(texts)

    dim = int(vectors.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(np.ascontiguousarray(vectors, dtype=np.float32))

    store = PersistedVectorStore(index=index, embedding_model=emb_model, chunks=chunks)

    if index_dir != ":memory:":
        out_dir = Path(index_dir) if index_dir is not None else DEFAULT_INDEX_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(out_dir / "knowledge.faiss"))
        joblib.dump(
            {"embedding_model": emb_model, "chunks": chunks},
            out_dir / "knowledge_meta.joblib",
        )

    return store


def load_persisted_vector_store(index_dir: Path | str | None = None) -> PersistedVectorStore | None:
    out_dir = Path(index_dir) if index_dir is not None else DEFAULT_INDEX_DIR
    faiss_file = out_dir / "knowledge.faiss"
    meta_file = out_dir / "knowledge_meta.joblib"
    if not faiss_file.exists() or not meta_file.exists():
        return None
    try:
        index = faiss.read_index(str(faiss_file))
        meta = joblib.load(meta_file)
        emb_model = meta.get("embedding_model")
        chunks = meta.get("chunks")
        if not isinstance(emb_model, EmbeddingModel) or not isinstance(chunks, list) or not chunks:
            return None
        return PersistedVectorStore(index=index, embedding_model=emb_model, chunks=chunks)
    except Exception:
        return None