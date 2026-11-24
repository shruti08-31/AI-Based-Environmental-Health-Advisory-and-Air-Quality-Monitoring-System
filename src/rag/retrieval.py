from dataclasses import dataclass
from pathlib import Path

from src.rag.document_loader import DEFAULT_KB_DIR, load_and_chunk_documents
from src.rag.vector_store import (
    DEFAULT_INDEX_DIR,
    PersistedVectorStore,
    build_and_persist_vector_store,
    load_persisted_vector_store,
)


@dataclass(frozen=True)
class RetrievedContext:
    chunk_id: str
    title: str
    source: str
    score: float
    text: str


def get_or_build_vector_store(
    kb_dir: Path | str | None = None,
    index_dir: Path | str | None = None,
    force_rebuild: bool = False,
) -> PersistedVectorStore:
    if not force_rebuild and index_dir != ":memory:":
        existing = load_persisted_vector_store(index_dir=index_dir)
        if existing is not None:
            return existing

    chunks = load_and_chunk_documents(kb_dir=kb_dir or DEFAULT_KB_DIR)
    return build_and_persist_vector_store(chunks, index_dir=index_dir or DEFAULT_INDEX_DIR)


def retrieve_relevant_knowledge(
    query: str,
    top_k: int = 3,
    min_score: float = 0.05,
    kb_dir: Path | str | None = None,
    index_dir: Path | str | None = None,
    vector_store: PersistedVectorStore | None = None,
) -> list[RetrievedContext]:
    store = vector_store or get_or_build_vector_store(kb_dir=kb_dir, index_dir=index_dir)
    matches = store.search(query, top_k=top_k)

    results: list[RetrievedContext] = []
    for chunk, score in matches:
        if score < min_score:
            continue
        results.append(
            RetrievedContext(
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                source=chunk.source,
                score=score,
                text=chunk.text,
            )
        )
    return results