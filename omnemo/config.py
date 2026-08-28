"""Configuration: exposed defaults, optionally overridden by a TOML file.

Every ranking weight, threshold, and category parameter lives here — never
hard-coded at the point of use — so recall can be tuned on real data
without touching code.

Config file: $XDG_CONFIG_HOME/omnemo/config.toml (default ~/.config/omnemo/).
Missing file or missing keys fall back to the shipped defaults below.
Invalid values fail at load time with a ConfigError naming the key —
hand-edited TOML is the supported tuning surface, so it must never crash
a verb with a raw traceback later.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """config.toml contains an invalid value."""


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "omnemo" / "config.toml"


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "omnemo"


def store_path() -> Path:
    return data_dir() / "store.db"


@dataclass(frozen=True)
class Category:
    """Per-category ranking parameters.

    importance: additive weight in the composite recall score (0..1).
    half_life_multiplier: scales the base recency half-life — memories in
    a category with multiplier 2.0 fade half as fast as the base rate.
    """

    importance: float
    half_life_multiplier: float


DEFAULT_CATEGORIES: dict[str, Category] = {
    "fact": Category(importance=0.6, half_life_multiplier=4.0),
    "decision": Category(importance=1.0, half_life_multiplier=6.0),
    "preference": Category(importance=0.8, half_life_multiplier=8.0),
    "incident": Category(importance=0.9, half_life_multiplier=2.0),
    "transient": Category(importance=0.2, half_life_multiplier=0.25),
}


@dataclass(frozen=True)
class Config:
    # Embedder spec: "fastembed:<model-name>".
    embedder: str = "fastembed:BAAI/bge-small-en-v1.5"

    # Recall ranking — composite score:
    #   score = weight_similarity * cosine_similarity
    #         + weight_recency    * 0.5 ** (age_days / (base_half_life_days * category.half_life_multiplier))
    #         + weight_importance * category.importance
    #         + weight_recall_count * min(recall_count, recall_count_cap) / recall_count_cap
    # Candidates below min_similarity are dropped before scoring.
    min_similarity: float = 0.35
    weight_similarity: float = 1.0
    weight_recency: float = 0.25
    weight_importance: float = 0.15
    weight_recall_count: float = 0.10
    base_half_life_days: float = 30.0
    recall_count_cap: int = 10

    default_category: str = "fact"
    recall_limit: int = 5
    search_limit: int = 20

    # Parameters used for memories whose saved category is no longer in
    # the config (removed or renamed): recall degrades, never crashes.
    fallback_importance: float = 0.5
    fallback_half_life_multiplier: float = 1.0

    categories: dict[str, Category] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORIES)
    )


_SCALAR_TYPES: dict[str, type] = {
    "embedder": str,
    "min_similarity": float,
    "weight_similarity": float,
    "weight_recency": float,
    "weight_importance": float,
    "weight_recall_count": float,
    "base_half_life_days": float,
    "recall_count_cap": int,
    "default_category": str,
    "recall_limit": int,
    "search_limit": int,
    "fallback_importance": float,
    "fallback_half_life_multiplier": float,
}


def _scalar(key: str, value: object) -> object:
    expected = _SCALAR_TYPES[key]
    is_bool = isinstance(value, bool)
    if expected is float and isinstance(value, (int, float)) and not is_bool:
        return float(value)
    if expected is int and isinstance(value, int) and not is_bool:
        return value
    if expected is str and isinstance(value, str):
        return value
    kind = {float: "number", int: "integer", str: "string"}[expected]
    raise ConfigError(f"{key} must be a {kind} (got {value!r})")


def _number(name: str, value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise ConfigError(f"{name} must be a number (got {value!r})")


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML, merging over the shipped defaults.

    Raises ConfigError with the offending key named for any invalid value.
    """
    path = path if path is not None else config_path()
    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    kwargs: dict = {k: _scalar(k, raw[k]) for k in _SCALAR_TYPES if k in raw}

    defaults = Config()
    # Base for categories new to this file that omit a field.
    new_base = Category(
        importance=kwargs.get("fallback_importance", defaults.fallback_importance),
        half_life_multiplier=kwargs.get(
            "fallback_half_life_multiplier", defaults.fallback_half_life_multiplier
        ),
    )

    raw_categories = raw.get("categories", {})
    if not isinstance(raw_categories, dict):
        raise ConfigError(f"categories must be a table (got {raw_categories!r})")
    categories = dict(DEFAULT_CATEGORIES)
    for name, params in raw_categories.items():
        if not isinstance(params, dict):
            raise ConfigError(f"categories.{name} must be a table (got {params!r})")
        base = categories.get(name, new_base)
        categories[name] = Category(
            importance=_number(
                f"categories.{name}.importance",
                params.get("importance", base.importance),
            ),
            half_life_multiplier=_number(
                f"categories.{name}.half_life_multiplier",
                params.get("half_life_multiplier", base.half_life_multiplier),
            ),
        )
    kwargs["categories"] = categories

    config = Config(**kwargs)
    _validate(config)
    return config


def _validate(config: Config) -> None:
    if config.base_half_life_days <= 0:
        raise ConfigError(
            f"base_half_life_days must be positive (got {config.base_half_life_days})"
        )
    if config.fallback_half_life_multiplier <= 0:
        raise ConfigError(
            "fallback_half_life_multiplier must be positive "
            f"(got {config.fallback_half_life_multiplier})"
        )
    for name, cat in config.categories.items():
        if cat.half_life_multiplier <= 0:
            raise ConfigError(
                f"categories.{name}.half_life_multiplier must be positive "
                f"(got {cat.half_life_multiplier})"
            )
    if config.recall_count_cap < 1:
        raise ConfigError(
            f"recall_count_cap must be >= 1 (got {config.recall_count_cap})"
        )
    if config.recall_limit < 1:
        raise ConfigError(f"recall_limit must be >= 1 (got {config.recall_limit})")
    if config.search_limit < 1:
        raise ConfigError(f"search_limit must be >= 1 (got {config.search_limit})")
    if config.default_category not in config.categories:
        known = ", ".join(sorted(config.categories))
        raise ConfigError(
            f"default_category {config.default_category!r} is not a "
            f"configured category (known: {known})"
        )
