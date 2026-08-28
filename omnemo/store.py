"""SQLite memory store: save / recall / search / forget.

Schema (see docs/core.md):
  meta       — key/value store metadata; records the embedder name and
               dimension so a store is never opened under a different
               embedder (mixed vector spaces silently break recall).
  memories   — id, text, category, created_at, last_recalled_at,
               recall_count. Forget DELETEs the row — no tombstones.
  embeddings — one vector per memory, keyed by memory id, deleted by
               cascade when the memory is forgotten.
"""

from __future__ import annotations

import math
import sqlite3
import threading
import time
from array import array
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from .config import FALLBACK_CATEGORY, Config
from .embedder import Embedder

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    text             TEXT NOT NULL,
    category         TEXT NOT NULL,
    created_at       REAL NOT NULL,
    last_recalled_at REAL,
    recall_count     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS embeddings (
    memory_id INTEGER PRIMARY KEY
              REFERENCES memories(id) ON DELETE CASCADE,
    vector    BLOB NOT NULL
);
"""


class EmbedderMismatchError(Exception):
    """The store was created with a different embedder than the one
    configured now. Refusing to mix vector spaces."""


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    category: str
    created_at: float
    last_recalled_at: float | None
    recall_count: int


@dataclass(frozen=True)
class RecallResult:
    memory: Memory
    similarity: float
    score: float


def _pack(vec: list[float]) -> bytes:
    return array("f", vec).tobytes()


def _unpack(blob: bytes) -> list[float]:
    a = array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Store:
    """One human's memory store. One embedder per store, enforced."""

    def __init__(self, path: Path, embedder: Embedder, config: Config) -> None:
        self.embedder = embedder
        self.config = config
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the MCP SDK runs sync tool functions on
        # worker threads, and concurrent tool calls are possible. self._lock
        # serializes DB access so one verb's transaction can never interleave
        # with another's (e.g. a commit landing between save's two INSERTs).
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._check_embedder()

    def _check_embedder(self) -> None:
        rows = dict(
            self._conn.execute(
                "SELECT key, value FROM meta "
                "WHERE key IN ('embedder_name', 'embedder_dim')"
            ).fetchall()
        )
        if not rows:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('embedder_name', ?)",
                (self.embedder.name,),
            )
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('embedder_dim', ?)",
                (str(self.embedder.dim),),
            )
            self._conn.commit()
            return
        stored = f"{rows['embedder_name']} (dim {rows['embedder_dim']})"
        configured = f"{self.embedder.name} (dim {self.embedder.dim})"
        if stored != configured:
            self._conn.close()
            raise EmbedderMismatchError(
                f"store was created with embedder {stored}, "
                f"but {configured} is configured. "
                "One embedder per store — use the original embedder "
                "or start a new store."
            )

    def close(self) -> None:
        self._conn.close()

    # -- the four verbs ------------------------------------------------

    def save(self, text: str, category: str | None = None) -> Memory:
        category = category or self.config.default_category
        if category not in self.config.categories:
            known = ", ".join(sorted(self.config.categories))
            raise ValueError(f"unknown category {category!r} (known: {known})")
        vector = self.embedder.embed([text])[0]
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO memories (text, category, created_at) VALUES (?, ?, ?)",
                (text, category, now),
            )
            memory_id = cur.lastrowid
            assert memory_id is not None
            self._conn.execute(
                "INSERT INTO embeddings (memory_id, vector) VALUES (?, ?)",
                (memory_id, _pack(vector)),
            )
            self._conn.commit()
        return Memory(memory_id, text, category, now, None, 0)

    def recall(self, query: str, limit: int | None = None) -> list[RecallResult]:
        """Semantic recall, ranked by the composite score (docs/core.md).

        Returned memories get their recall stats updated.
        """
        cfg = self.config
        limit = limit if limit is not None else cfg.recall_limit
        query_vec = self.embedder.embed([query])[0]
        now = time.time()

        with self._lock:
            results: list[RecallResult] = []
            rows = self._conn.execute(
                "SELECT m.*, e.vector FROM memories m "
                "JOIN embeddings e ON e.memory_id = m.id"
            ).fetchall()
            for row in rows:
                similarity = _cosine(query_vec, _unpack(row["vector"]))
                if similarity < cfg.min_similarity:
                    continue
                # Fallback covers memories saved under a category since
                # removed from config — recall degrades, never crashes.
                cat = cfg.categories.get(row["category"], FALLBACK_CATEGORY)
                age_days = max(0.0, now - row["created_at"]) / 86400.0
                half_life = cfg.base_half_life_days * cat.half_life_multiplier
                recency = 0.5 ** (age_days / half_life)
                count_term = min(row["recall_count"], cfg.recall_count_cap) / cfg.recall_count_cap
                score = (
                    cfg.weight_similarity * similarity
                    + cfg.weight_recency * recency
                    + cfg.weight_importance * cat.importance
                    + cfg.weight_recall_count * count_term
                )
                results.append(RecallResult(_row_to_memory(row), similarity, score))

            results.sort(key=lambda r: r.score, reverse=True)
            results = results[:limit]

            for r in results:
                self._conn.execute(
                    "UPDATE memories SET last_recalled_at = ?, recall_count = recall_count + 1 "
                    "WHERE id = ?",
                    (now, r.memory.id),
                )
            self._conn.commit()
        return results

    def search(self, query: str, limit: int = 20) -> list[Memory]:
        """Literal substring search (case-insensitive). No embedding, and
        no recall-stat updates — this is for browsing, not remembering."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE text LIKE ? ESCAPE '\\' "
                "ORDER BY created_at DESC LIMIT ?",
                (f"%{_escape_like(query)}%", limit),
            ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def forget(self, memory_id: int) -> bool:
        """DELETE the memory and its embedding. Gone from the store,
        not just deranked. Returns False if the id did not exist."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self._conn.commit()
        return cur.rowcount > 0

    # -- stats ---------------------------------------------------------

    def stats(self) -> dict:
        midnight = (
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            learned_today = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE created_at >= ?", (midnight,)
            ).fetchone()[0]
            last = self._conn.execute(
                "SELECT MAX(last_recalled_at) FROM memories"
            ).fetchone()[0]
        return {
            "memory_count": count,
            "learned_today": learned_today,
            "last_recall_at": last,
        }


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        text=row["text"],
        category=row["category"],
        created_at=row["created_at"],
        last_recalled_at=row["last_recalled_at"],
        recall_count=row["recall_count"],
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
