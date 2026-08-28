"""Config loading: shipped defaults, TOML overrides, category merging."""

from pathlib import Path

import pytest

from omnemo.config import DEFAULT_CATEGORIES, Config, ConfigError, load_config


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
        'embedder = "fastembed:custom-model"\n'
        "min_similarity = 0.5\n"
        "[categories.fact]\n"
        "importance = 0.9\n"
        "[categories.recipe]\n"
        "importance = 0.7\n"
        "half_life_multiplier = 12.0\n"
    )
    config = load_config(path)

    assert config.embedder == "fastembed:custom-model"
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


@pytest.mark.parametrize(
    ("toml", "match"),
    [
        ("recall_count_cap = 0\n", "recall_count_cap"),
        ("base_half_life_days = 0\n", "base_half_life_days"),
        (
            "[categories.fact]\nhalf_life_multiplier = 0\n",
            "categories.fact.half_life_multiplier",
        ),
        ('recall_limit = "five"\n', "recall_limit"),
        ('[categories]\nfact = "high"\n', "categories.fact must be a table"),
        ('categories = "all of them"\n', "categories must be a table"),
        ('default_category = "daydream"\n', "default_category"),
        ("search_limit = 0\n", "search_limit"),
        ("fallback_half_life_multiplier = -1\n", "fallback_half_life_multiplier"),
        ("min_similarity = true\n", "min_similarity"),
    ],
)
def test_invalid_values_fail_at_load(tmp_path, toml: str, match: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(toml)
    with pytest.raises(ConfigError, match=match):
        load_config(path)


def test_fallback_and_search_limit_configurable(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "search_limit = 3\n"
        "fallback_importance = 0.1\n"
        "fallback_half_life_multiplier = 2.5\n"
    )
    config = load_config(path)
    assert config.search_limit == 3
    assert config.fallback_importance == 0.1
    assert config.fallback_half_life_multiplier == 2.5
