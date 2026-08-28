"""Embedders: local only, one per store.

The store records which embedder produced its vectors and refuses to open
under a different one — mixing embedders fragments the vector space and
silently breaks recall.

No provider API keys are ever read from the environment; embedding never
leaves the machine (fastembed's one-time model download excepted).
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol


class Embedder(Protocol):
    """A text embedder. `name` identifies it in store metadata; `dim` is the
    vector length. Both must be stable for the life of a store."""

    @property
    def name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def warm_up(self) -> None:
        """Load the model and run one embedding so first real use is fast."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Local ONNX embedder via the fastembed package.

    The model is downloaded once to fastembed's cache on first use; after
    that everything runs offline.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model = None
        self._dim: int | None = None

    @property
    def name(self) -> str:
        return f"fastembed:{self._model_name}"

    @property
    def dim(self) -> int:
        if self._dim is None:
            # Known models: read the dimension from fastembed's registry so
            # opening a store (which checks it) never forces a model load.
            from fastembed import TextEmbedding

            for entry in TextEmbedding.list_supported_models():
                if entry["model"] == self._model_name:
                    self._dim = int(entry["dim"])
                    break
            else:
                self.warm_up()
        assert self._dim is not None
        return self._dim

    def warm_up(self) -> None:
        if self._model is None:
            from fastembed import TextEmbedding  # deferred: heavy import

            self._model = TextEmbedding(model_name=self._model_name)
            self._dim = len(next(iter(self._model.embed(["warm up"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.warm_up()
        assert self._model is not None
        return [[float(x) for x in vec] for vec in self._model.embed(texts)]


class FakeEmbedder:
    """Deterministic bag-of-words hash embedder — for tests and offline
    smoke runs only. Shared words produce similar vectors; no semantics."""

    def __init__(self, name: str = "fake:v1", dim: int = 64) -> None:
        self._name = name
        self._dim = dim

    @property
    def name(self) -> str:
        return self._name

    @property
    def dim(self) -> int:
        return self._dim

    def warm_up(self) -> None:
        return None

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in text.lower().split():
            token = token.strip(".,;:!?\"'()[]")
            if not token:
                continue
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self._dim
            vec[index] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


def make_embedder(spec: str) -> Embedder:
    """Build an embedder from a config spec string.

    "fastembed:<model>" — local ONNX model (the default).
    "fake"              — deterministic test embedder.
    """
    if spec == "fake":
        return FakeEmbedder()
    if spec.startswith("fastembed:"):
        return FastEmbedEmbedder(spec.removeprefix("fastembed:"))
    raise ValueError(f"unknown embedder spec: {spec!r}")
