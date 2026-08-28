"""Configuration: exposed defaults, optionally overridden by a TOML file.

Every ranking weight, threshold, and category parameter lives here — never
hard-coded at the point of use — so recall can be tuned on real data
without touching code.

Config file: $XDG_CONFIG_HOME/omnemo/config.toml (default ~/.config/omnemo/).
Missing file or missing keys fall back to the shipped defaults below.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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
    # Embedder spec: "fastembed:<model-name>" or "fake" (deterministic,
    # for tests / offline smoke runs — not a real semantic model).
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

    categories: dict[str, Category] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORIES)
    )


_SCALAR_KEYS = (
    "embedder",
    "min_similarity",
    "weight_similarity",
    "weight_recency",
    "weight_importance",
    "weight_recall_count",
    "base_half_life_days",
    "recall_count_cap",
    "default_category",
    "recall_limit",
)


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML, merging over the shipped defaults."""
    path = path if path is not None else config_path()
    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    kwargs: dict = {k: raw[k] for k in _SCALAR_KEYS if k in raw}

    categories = dict(DEFAULT_CATEGORIES)
    for name, params in raw.get("categories", {}).items():
        base = categories.get(name, Category(importance=0.5, half_life_multiplier=1.0))
        categories[name] = Category(
            importance=float(params.get("importance", base.importance)),
            half_life_multiplier=float(
                params.get("half_life_multiplier", base.half_life_multiplier)
            ),
        )
    kwargs["categories"] = categories

    return Config(**kwargs)
