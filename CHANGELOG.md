# Omnemo Changelog

## Unreleased

- omnemo-core v0.1 skeleton (0.1.0.dev0): memory-only MCP server over stdio
  with the four verbs (save / recall / search / forget), SQLite store in the
  XDG data dir, local fastembed embeddings (one embedder per store, mismatch
  refused), composite recall ranking with category-aware decay, all weights
  and thresholds in `config.toml`, CLI (`serve` + direct verbs + `stats`),
  pytest suite, `docs/core.md`. Omarchy glove pieces (skill, widget, hooks,
  `connect`) not yet built.

- Spec v0.2 (2026-08-28): architect review folded in — embeddings local-first (hybrid key-discovery rejected), conservative auto-save, stats-only digest, forget + connect read-back criteria, single-user guarantee.

- Project born 2026-08-28: name chosen, spec v0.1 drafted (see SPEC.md).
