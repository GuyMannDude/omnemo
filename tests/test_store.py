"""Store behavior: the four verbs, forget-forgets, ranking, mismatch refusal."""

import sqlite3
import time
from pathlib import Path

import pytest

from fake_embedder import FakeEmbedder

from omnemo.config import Category, Config
from omnemo.store import CorruptStoreError, EmbedderMismatchError, Store


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
        categories={**Config().categories, "recipe": Category(0.7, 12.0)},
    )
    store = Store(path, FakeEmbedder(), with_recipe)
    saved = store.save("Sourdough starter needs feeding every morning", "recipe")
    store.close()

    store = Store(path, FakeEmbedder(), Config())
    try:
        ids = [r.memory.id for r in store.recall("when does the sourdough starter need feeding")]
        assert saved.id in ids
    finally:
        store.close()


def test_min_similarity_threshold(tmp_path: Path) -> None:
    # This pair's fake-embedder similarity measures ~0.41 — between the
    # two thresholds — so the memory is recalled under the lower floor
    # and filtered by the higher one. (A zero-overlap pair would pass
    # for any threshold > 0 and prove nothing.)
    text = "The bicycle tyre pressure gauge lives in the shed drawer"
    query = "how often does the bicycle tyre need air"
    path = tmp_path / "s.db"

    low = Store(path, FakeEmbedder(), Config(min_similarity=0.35))
    try:
        saved = low.save(text)
        results = low.recall(query)
        assert [r.memory.id for r in results] == [saved.id]
        assert 0.35 < results[0].similarity < 0.45
    finally:
        low.close()

    high = Store(path, FakeEmbedder(), Config(min_similarity=0.45))
    try:
        assert high.recall(query) == []
    finally:
        high.close()


def test_embedder_mismatch_refused(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    store = Store(path, FakeEmbedder(name="fake:aaa"), Config())
    store.save("a memory")
    store.close()

    with pytest.raises(EmbedderMismatchError, match="fake:aaa"):
        Store(path, FakeEmbedder(name="fake:bbb"), Config())

    # Same embedder reopens fine.
    reopened = Store(path, FakeEmbedder(name="fake:aaa"), Config())
    assert reopened.stats()["memory_count"] == 1
    reopened.close()


def test_embedder_dim_mismatch_refused(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    Store(path, FakeEmbedder(name="fake:v1", dim=64), Config()).close()
    with pytest.raises(EmbedderMismatchError, match="dim 64"):
        Store(path, FakeEmbedder(name="fake:v1", dim=32), Config())


def test_corrupt_meta_reports_cleanly(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    Store(path, FakeEmbedder(), Config()).close()

    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM meta WHERE key = 'embedder_dim'")
    conn.commit()
    conn.close()

    with pytest.raises(CorruptStoreError, match="embedder_dim"):
        Store(path, FakeEmbedder(), Config())


def test_store_is_private_to_owner(tmp_path: Path) -> None:
    path = tmp_path / "data" / "store.db"
    store = Store(path, FakeEmbedder(), Config())
    try:
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        store.close()

    # Pre-existing, too-open directory gets tightened on open.
    path.parent.chmod(0o755)
    path.chmod(0o644)
    store = Store(path, FakeEmbedder(), Config())
    try:
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        store.close()


def test_secure_delete_is_on(store: Store) -> None:
    # Forgotten plaintext must not linger in freelist pages; the SQLite
    # compile-time default is OFF, so the store must set it explicitly.
    assert store._conn.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_stats(store: Store) -> None:
    assert store.stats() == {
        "memory_count": 0,
        "superseded": 0,
        "learned_today": 0,
        "last_recall_at": None,
    }
    store.save("Learned a thing today")
    store.recall("thing learned")
    s = store.stats()
    assert s["memory_count"] == 1
    assert s["learned_today"] == 1
    assert s["last_recall_at"] is not None


# -- truth changes: near-duplicate signal + supersede (0.2.0) -------------


def test_save_reports_near_duplicates_but_still_lands(store: Store) -> None:
    old = store.save("The test rig is alive and serving on port 9000")
    assert old.near_duplicates == []
    new = store.save("The test rig is alive and serving on port 9000 today")
    assert new.id != old.id
    assert [n.memory.id for n in new.near_duplicates] == [old.id]
    assert new.near_duplicates[0].similarity >= store.config.near_duplicate_similarity
    # Both live: nothing was held or demoted.
    assert {r.memory.id for r in store.recall("test rig port")} == {old.id, new.id}


def test_near_duplicates_ignore_unrelated_and_superseded(store: Store) -> None:
    unrelated = store.save("The cat prefers the window seat")
    old = store.save("The test rig is alive and serving on port 9000")
    mid = store.save("The test rig is alive and serving on port 9000 still", supersedes=[old.id])
    assert unrelated.id not in [n.memory.id for n in mid.near_duplicates]
    # old is superseded now, so a third near-identical save sees only mid.
    third = store.save("The test rig is alive and serving on port 9000 again")
    assert [n.memory.id for n in third.near_duplicates] == [mid.id]


def test_supersede_hides_old_from_recall_but_not_search(store: Store) -> None:
    old = store.save("The rig is alive", category="fact")
    new = store.save("The rig is decommissioned", category="fact", supersedes=[old.id])
    ids = [r.memory.id for r in store.recall("is the rig alive")]
    assert new.id in ids
    assert old.id not in ids
    browse = {m.id: m for m in store.search("rig")}
    assert browse[old.id].superseded_by == new.id
    assert browse[new.id].superseded_by is None


def test_forgetting_the_superseder_restores_the_old_claim(store: Store) -> None:
    old = store.save("The rig is alive")
    new = store.save("The rig is decommissioned", supersedes=[old.id])
    assert old.id not in [r.memory.id for r in store.recall("rig alive")]
    assert store.forget(new.id) is True
    assert old.id in [r.memory.id for r in store.recall("rig alive")]
    assert store.search("rig")[0].superseded_by is None


def test_supersede_unknown_id_writes_nothing(store: Store) -> None:
    before = store.stats()["memory_count"]
    with pytest.raises(ValueError, match="unknown memory id"):
        store.save("The rig is decommissioned", supersedes=[9999])
    assert store.stats()["memory_count"] == before


def test_old_store_gains_superseded_by_column(tmp_path: Path) -> None:
    """A store written by 0.1.x has no superseded_by column; opening it
    under 0.2.0 migrates in place and keeps the rows."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,
            category TEXT NOT NULL, created_at REAL NOT NULL,
            last_recalled_at REAL, recall_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE embeddings (
            memory_id INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
            vector BLOB NOT NULL);
        INSERT INTO meta VALUES ('embedder_name', 'fake:v1'), ('embedder_dim', '64');
        """
    )
    conn.commit()
    conn.close()
    store = Store(path, FakeEmbedder(), Config())
    try:
        cols = {r[1] for r in store._conn.execute("PRAGMA table_info(memories)")}
        assert "superseded_by" in cols
        old = store.save("The rig is alive")
        new = store.save("The rig is decommissioned", supersedes=[old.id])
        assert [r.memory.id for r in store.recall("rig")] == [new.id]
        # The ALTER-added foreign key must be enforced: forgetting the
        # superseder restores the old row (ON DELETE SET NULL).
        assert store.forget(new.id) is True
        assert [r.memory.id for r in store.recall("rig")] == [old.id]
    finally:
        store.close()


def test_cannot_resupersede_a_retired_memory(store: Store) -> None:
    """Re-pointing a retired row would let forget() of the second superseder
    resurrect the stale claim beside the memory that already replaced it."""
    old = store.save("The rig is alive")
    second = store.save("The rig is decommissioned", supersedes=[old.id])
    with pytest.raises(ValueError, match="already superseded"):
        store.save("The rig is scrapped", supersedes=[old.id])
    assert store.stats()["memory_count"] == 2
    ids = [r.memory.id for r in store.recall("rig")]
    assert ids == [second.id]


def test_supersedes_accepts_string_ids_and_rejects_junk(store: Store) -> None:
    old = store.save("The rig is alive")
    new = store.save("The rig is decommissioned", supersedes=[str(old.id)])
    assert {m.id: m.superseded_by for m in store.search("rig")}[old.id] == new.id
    with pytest.raises(ValueError, match="must be an integer"):
        store.save("junk", supersedes=["abc"])


def test_near_duplicate_limit_zero_turns_the_scan_off(tmp_path: Path) -> None:
    s = Store(tmp_path / "s.db", FakeEmbedder(), Config(near_duplicate_limit=0))
    try:
        s.save("The rig is alive")
        assert s.save("The rig is alive").near_duplicates == []
    finally:
        s.close()


def test_near_duplicate_limit_truncates(tmp_path: Path) -> None:
    s = Store(tmp_path / "s.db", FakeEmbedder(), Config(near_duplicate_limit=2))
    try:
        for _ in range(3):
            s.save("The rig is alive")
        assert len(s.save("The rig is alive").near_duplicates) == 2
    finally:
        s.close()


def test_save_result_reads_through_every_memory_field(store: Store) -> None:
    r = store.save("The rig is alive")
    assert r.created_at == r.memory.created_at
    assert r.recall_count == 0 and r.superseded_by is None
    with pytest.raises(AttributeError):
        r.nonexistent_field


def test_stats_counts_superseded(store: Store) -> None:
    old = store.save("The rig is alive")
    store.save("The rig is decommissioned", supersedes=[old.id])
    s = store.stats()
    assert s["memory_count"] == 2 and s["superseded"] == 1
