"""Store behavior: the four verbs, forget-forgets, ranking, mismatch refusal."""

import sqlite3
import time
from pathlib import Path

import pytest

from omnemo.config import Config
from omnemo.embedder import FakeEmbedder
from omnemo.store import EmbedderMismatchError, Store


def test_save_and_recall(store: Store) -> None:
    saved = store.save("The deploy password lives on the blue USB stick")
    assert saved.id > 0
    assert saved.category == "fact"

    results = store.recall("where is the deploy password")
    assert results
    assert results[0].memory.id == saved.id
    assert results[0].similarity > 0


def test_recall_updates_stats(store: Store) -> None:
    saved = store.save("Coffee machine descale ritual happens monthly")
    store.recall("coffee machine descale")

    row = store._conn.execute(
        "SELECT recall_count, last_recalled_at FROM memories WHERE id = ?",
        (saved.id,),
    ).fetchone()
    assert row["recall_count"] == 1
    assert row["last_recalled_at"] is not None


def test_search_literal(store: Store) -> None:
    store.save("Fixed the printer by power cycling it twice")
    store.save("The cat prefers the window seat")

    hits = store.search("printer")
    assert len(hits) == 1
    assert "printer" in hits[0].text
    assert store.search("submarine") == []


def test_search_escapes_like_wildcards(store: Store) -> None:
    store.save("Progress is at 100% today")
    store.save("Progress is at 100 percent today")
    hits = store.search("100%")
    assert len(hits) == 1


def test_forget_forgets(store: Store) -> None:
    keep = store.save("The garden gate code is green")
    drop = store.save("The garage door code is red")

    assert store.forget(drop.id) is True

    # Not recalled any more...
    ids = [r.memory.id for r in store.recall("what is the garage door code")]
    assert drop.id not in ids
    assert keep.id in ids

    # ...and the rows are physically gone, embedding included.
    assert (
        store._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE id = ?", (drop.id,)
        ).fetchone()[0]
        == 0
    )
    assert (
        store._conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE memory_id = ?", (drop.id,)
        ).fetchone()[0]
        == 0
    )


def test_forget_unknown_id(store: Store) -> None:
    assert store.forget(9999) is False


def test_save_rejects_unknown_category(store: Store) -> None:
    with pytest.raises(ValueError, match="unknown category"):
        store.save("something", category="daydream")


def test_ranking_similar_recent_beats_dissimilar_old(store: Store) -> None:
    old = store.save("The kitchen tap drips when the heating is on")
    new = store.save("The bicycle tyre needs air every single week")

    # Age the first memory by a year.
    store._conn.execute(
        "UPDATE memories SET created_at = ? WHERE id = ?",
        (time.time() - 365 * 86400, old.id),
    )
    store._conn.commit()

    results = store.recall("how often does the bicycle tyre need air")
    assert results[0].memory.id == new.id
    if len(results) > 1:
        assert results[0].score > results[1].score


def test_min_similarity_threshold(tmp_path: Path) -> None:
    config = Config(embedder="fake", min_similarity=0.99)
    store = Store(tmp_path / "s.db", FakeEmbedder(), config)
    try:
        store.save("Entirely unrelated words about quantum marmalade")
        assert store.recall("bicycle maintenance schedule") == []
    finally:
        store.close()


def test_embedder_mismatch_refused(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    store = Store(path, FakeEmbedder(name="fake:aaa"), Config(embedder="fake"))
    store.save("a memory")
    store.close()

    with pytest.raises(EmbedderMismatchError, match="fake:aaa"):
        Store(path, FakeEmbedder(name="fake:bbb"), Config(embedder="fake"))

    # Same embedder reopens fine.
    reopened = Store(path, FakeEmbedder(name="fake:aaa"), Config(embedder="fake"))
    assert reopened.stats()["memory_count"] == 1
    reopened.close()


def test_stats(store: Store) -> None:
    assert store.stats() == {
        "memory_count": 0,
        "learned_today": 0,
        "last_recall_at": None,
    }
    store.save("Learned a thing today")
    store.recall("thing learned")
    s = store.stats()
    assert s["memory_count"] == 1
    assert s["learned_today"] == 1
    assert s["last_recall_at"] is not None
