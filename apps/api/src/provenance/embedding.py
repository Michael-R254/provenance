"""Query embedding. Must match ingest/src/ingest/embed.py exactly (checked by evals tests)."""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

EMBEDDING_DIM = 384
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    model_name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Local ONNX embeddings via fastembed. Loads (and if needed downloads) the model once."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.dim = EMBEDDING_DIM
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts))]


class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors for tests. Identical to the ingest version."""

    model_name = "fake-hash-bow"
    dim = EMBEDDING_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
