"""Deterministic bag-of-words hash embedder for tests — shared words
produce similar vectors; no semantics. Test-only: never shipped, because
one-embedder-per-store would make configuring it a one-way door into a
store that can't recall meaningfully."""

from __future__ import annotations

import hashlib
import math


class FakeEmbedder:
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
