# omnemo-core

Memory-only MCP server (stdio). Four tools: `save`, `recall`, `search`,
`forget`. Local-first: SQLite store, local ONNX embeddings, no cloud, no
API keys — provider keys are never read from the environment.

## Storage

SQLite at `$XDG_DATA_HOME/omnemo/store.db` (default
`~/.local/share/omnemo/store.db`). The store is one human's memory: the
directory is kept at mode 0700 and the database at 0600 (tightened on
open if a pre-existing directory is looser), and `secure_delete` is ON
so forgotten rows are zeroed, not left in freelist pages.

```
meta        key, value                 -- embedder_name, embedder_dim
memories    id, text, category, created_at, last_recalled_at, recall_count
embeddings  memory_id -> vector (float32 blob), ON DELETE CASCADE
```

- **Forget deletes.** `forget` removes the row and its embedding — the
  memory is gone from the store, not hidden or deranked. There is no
  `deleted` flag and no tombstone.
- **One embedder per store.** `meta` records the embedder (name and
  dimension) that produced the vectors; opening the store with a
  different one raises `EmbedderMismatchError` rather than mixing
  vector spaces.
- `recall` bumps `recall_count` and `last_recalled_at` on the memories it
  returns. `search` (literal substring browse) does not.

## Recall ranking

Candidates below `min_similarity` (cosine) are dropped. Survivors are
scored:

```
recency = 0.5 ^ (age_days / (base_half_life_days * category.half_life_multiplier))

score = weight_similarity   * cosine_similarity
      + weight_recency      * recency
      + weight_importance   * category.importance
      + weight_recall_count * min(recall_count, recall_count_cap) / recall_count_cap
```

Category-aware decay lives in the recency term: a category's
`half_life_multiplier` scales the base half-life, so `transient`
memories (multiplier 0.25) fade in days while `preference` (8.0) holds
for months.

## Configuration

`$XDG_CONFIG_HOME/omnemo/config.toml` (default
`~/.config/omnemo/config.toml`). Every key is optional; missing keys use
the shipped defaults, and invalid values are rejected at load time with
an error naming the key. Nothing here is hard-coded in the ranking
path — these are the tuning knobs.

| Key | Default | Meaning |
|---|---|---|
| `embedder` | `"fastembed:BAAI/bge-small-en-v1.5"` | Embedder spec: `"fastembed:<model>"` (local ONNX) |
| `min_similarity` | `0.35` | Cosine floor before a memory can be recalled |
| `weight_similarity` | `1.0` | Ranking weight: similarity term |
| `weight_recency` | `0.25` | Ranking weight: recency term |
| `weight_importance` | `0.15` | Ranking weight: category importance term |
| `weight_recall_count` | `0.10` | Ranking weight: recall-count term |
| `base_half_life_days` | `30.0` | Base recency half-life, scaled per category |
| `recall_count_cap` | `10` | Recall counts at/above this saturate the count term |
| `default_category` | `"fact"` | Category used when `save` gets none |
| `recall_limit` | `5` | Default max results from `recall` |
| `search_limit` | `20` | Default max results from `search` |
| `fallback_importance` | `0.5` | Importance used for memories whose category was removed from config |
| `fallback_half_life_multiplier` | `1.0` | Half-life multiplier for those same memories |

Categories (each `[categories.<name>]` with `importance`,
`half_life_multiplier`; overrides merge over these defaults, new
categories may be added). Memories saved under a category later removed
from config still recall, using the `fallback_*` parameters above:

| Category | importance | half_life_multiplier |
|---|---|---|
| `fact` | 0.6 | 4.0 |
| `decision` | 1.0 | 6.0 |
| `preference` | 0.8 | 8.0 |
| `incident` | 0.9 | 2.0 |
| `transient` | 0.2 | 0.25 |

Example override:

```toml
min_similarity = 0.45

[categories.decision]
half_life_multiplier = 10.0
```

## Embeddings

Default embedder is [fastembed](https://pypi.org/project/fastembed/)
running `BAAI/bge-small-en-v1.5` locally (ONNX). **First run downloads
the model** (~100 MB, to fastembed's cache); after that everything is
offline. `omnemo serve` warms the embedder at start so the first recall
is not paying model-load time.

## CLI

```
omnemo serve                 # run the MCP server on stdio
omnemo save "text" [-c CAT]  # direct verbs for testing
omnemo recall "query" [-n N]
omnemo search "substring" [-n N]
omnemo forget ID
omnemo stats                 # memory count, learned today, last recall
```

`omnemo stats` is the source for the (v0.1, stats-only) morning digest:
no LLM pass, straight from the store.
