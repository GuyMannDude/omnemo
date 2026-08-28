# Omnemo Changelog

## Unreleased

- Hardening from independent review: config values validated at load time
  (clean errors, no tracebacks from hand-edited TOML), store private to its
  owner (0700/0600, tightened on open), `secure_delete` ON so forgotten rows
  are zeroed, corrupt store metadata reported cleanly, first-run model-download
  failures diagnosed on stderr, search limit and category-fallback parameters
  moved into config, test-only fake embedder removed from the shipped package.

- omnemo-core v0.1 skeleton (0.1.0.dev0): memory-only MCP server over stdio
  with the four verbs (save / recall / search / forget), SQLite store in the
  XDG data dir, local fastembed embeddings (one embedder per store, mismatch
  refused), composite recall ranking with category-aware decay, all weights
  and thresholds in `config.toml`, CLI (`serve` + direct verbs + `stats`),
  pytest suite, `docs/core.md`. Omarchy glove pieces (skill, widget, hooks,
  `connect`) not yet built.

- Spec v0.2 (2026-08-28): architect review folded in — embeddings local-first (hybrid key-discovery rejected), conservative auto-save, stats-only digest, forget + connect read-back criteria, single-user guarantee.

- Project born 2026-08-28: name chosen, spec v0.1 drafted (see SPEC.md).
