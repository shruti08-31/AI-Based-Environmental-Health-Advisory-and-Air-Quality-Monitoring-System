from dataclasses import dataclass
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class EmbeddingModel:
    vectorizer: TfidfVectorizer
    svd: TruncatedSVD | None
    dimension: int

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        tfidf_mat = self.vectorizer.transform(texts)
        if self.svd is not None:
            dense = self.svd.transform(tfidf_mat)
        else:
            dense = tfidf_mat.toarray()
        arr = np.asarray(dense, dtype=np.float32)
        if arr.shape[1] < self.dimension:
            pad = np.zeros((arr.shape[0], self.dimension - arr.shape[1]), dtype=np.float32)
            arr = np.hstack([arr, pad])
        elif arr.shape[1] > self.dimension:
            arr = arr[:, : self.dimension]
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms > 1e-12, norms, 1.0)
        return (arr / norms).astype(np.float32)


def fit_embedding_model(corpus_texts: list[str], max_dim: int = 64) -> tuple[EmbeddingModel, np.ndarray]:
    if not corpus_texts:
        raise ValueError("Cannot fit embedding model on an empty corpus.")

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    tfidf_mat = vectorizer.fit_transform(corpus_texts)
    n_samples, n_features = tfidf_mat.shape

    max_possible = min(n_samples - 1, n_features - 1, max_dim)
    if max_possible >= 4:
        svd = TruncatedSVD(n_components=max_possible, random_state=42)
        dense = svd.fit_transform(tfidf_mat)
        dim = int(dense.shape[1])
    else:
        svd = None
        dense = tfidf_mat.toarray()
        dim = int(dense.shape[1])

    arr = np.asarray(dense, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    normalized = (arr / norms).astype(np.float32)

    model = EmbeddingModel(vectorizer=vectorizer, svd=svd, dimension=dim)
    return model, normalized