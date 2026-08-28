"""Store behavior: the four verbs, forget-forgets, ranking, mismatch refusal."""

import sqlite3
import time
from pathlib import Path

import pytest

from omnemo.config import Category, Config
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


def _age(store: Store, memory_id: int, days: float) -> None:
    store._conn.execute(
        "UPDATE memories SET created_at = ? WHERE id = ?",
        (time.time() - days * 86400, memory_id),
    )
    store._conn.commit()


def test_ranking_similar_recent_beats_dissimilar_old(store: Store) -> None:
    # Both share enough words with the query to clear min_similarity;
    # "new" shares more AND is a year fresher, so it must rank first.
    old = store.save("The bicycle tyre pressure gauge lives in the shed drawer")
    new = store.save("The bicycle tyre needs air every single week")
    _age(store, old.id, 365)

    results = store.recall("how often does the bicycle tyre need air")
    assert [r.memory.id for r in results] == [new.id, old.id]
    assert results[0].score > results[1].score


def test_ranking_category_decay_and_importance(store: Store) -> None:
    # Identical text, identical age: only the category parameters differ.
    # preference (importance 0.8, half-life x8) must outrank transient
    # (importance 0.2, half-life x0.25) via both score terms.
    transient = store.save("The blue mug is in the dishwasher", category="transient")
    preference = store.save("The blue mug is in the dishwasher", category="preference")
    _age(store, transient.id, 10)
    _age(store, preference.id, 10)

    results = store.recall("where is the blue mug")
    assert [r.memory.id for r in results] == [preference.id, transient.id]
    assert results[0].similarity == results[1].similarity
    assert results[0].score > results[1].score


def test_recall_survives_removed_category(tmp_path: Path) -> None:
    # A memory saved under a category later removed from config still
    # recalls (with fallback parameters) instead of crashing.
    path = tmp_path / "s.db"
    with_recipe = Config(
        embedder="fake",
        categories={**Config().categories, "recipe": Category(0.7, 12.0)},
    )
    store = Store(path, FakeEmbedder(), with_recipe)
    saved = store.save("Sourdough starter needs feeding every morning", "recipe")
    store.close()

    store = Store(path, FakeEmbedder(), Config(embedder="fake"))
    try:
        ids = [r.memory.id for r in store.recall("when does the sourdough starter need feeding")]
        assert saved.id in ids
    finally:
        store.close()


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


def test_embedder_dim_mismatch_refused(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    Store(path, FakeEmbedder(name="fake:v1", dim=64), Config(embedder="fake")).close()
    with pytest.raises(EmbedderMismatchError, match="dim 64"):
        Store(path, FakeEmbedder(name="fake:v1", dim=32), Config(embedder="fake"))


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
