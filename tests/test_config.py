"""Config loading: shipped defaults, TOML overrides, category merging."""

from pathlib import Path

from omnemo.config import DEFAULT_CATEGORIES, Config, load_config


def test_defaults_without_file(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does-not-exist.toml")
    assert config == Config()
    assert config.min_similarity == 0.35
    assert config.weight_similarity == 1.0
    assert config.embedder.startswith("fastembed:")
    assert set(config.categories) == {
        "fact",
        "decision",
        "preference",
        "incident",
        "transient",
    }


def test_partial_override_merges_over_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'embedder = "fake"\n'
        "min_similarity = 0.5\n"
        "[categories.fact]\n"
        "importance = 0.9\n"
        "[categories.recipe]\n"
        "importance = 0.7\n"
        "half_life_multiplier = 12.0\n"
    )
    config = load_config(path)

    assert config.embedder == "fake"
    assert config.min_similarity == 0.5
    # Untouched keys keep their defaults.
    assert config.weight_recency == Config().weight_recency
    # Existing category: overridden field changes, the other is kept.
    assert config.categories["fact"].importance == 0.9
    assert (
        config.categories["fact"].half_life_multiplier
        == DEFAULT_CATEGORIES["fact"].half_life_multiplier
    )
    # New category is added alongside the defaults.
    assert config.categories["recipe"].half_life_multiplier == 12.0
    assert "transient" in config.categories
