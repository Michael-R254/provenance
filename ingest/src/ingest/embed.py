"""Embedding models behind one small interface."""

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
    """Local ONNX embeddings via fastembed. Downloads the model on first use."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.dim = EMBEDDING_DIM
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts))]


class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors for tests. No model, no network.

    Texts that share words get similar vectors, which is enough to test ranking logic.
    """

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


def embedding_input(title: str, section: str, text: str) -> str:
    """The text that is embedded: chunk text with its document and section for context."""
    return f"{title} | {section}\n\n{text}"
