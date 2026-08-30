# Omnemo Changelog

## 0.1.1 — 2026-08-30

- Fix: `omnemo --version` (and the MCP server's advertised version) reported
  the stale hardcoded `0.1.0.dev0` on the released 0.1.0 — the version lived
  in two places and only one was bumped at release. `__version__` now reads
  from installed package metadata, so pyproject is the single source.

## 0.1.0 — 2026-08-30

First public release, on PyPI as `omnemo`. Everything below shipped in it,
capped by the live cross-harness proof: a memory saved by Claude Code
(Anthropic) recalled by Codex (OpenAI) through `omnemo/recall` on the
reference Omarchy 4.0.1 box — the problem (harness-local memory) fixed
by one shared store.

- Review hardening (independent review of the glove, 2026-08-28): JSON
  config rewrites now preserve the file's permission bits (a fresh temp
  file under the umask silently widened a user's 0600 key-bearing config
  to world-readable) and the temp copy is created 0600; CLI-adapter
  read-back is four-state (unknown/absent/ok/stale) — a broken harness
  CLI now fails disconnect instead of claiming "was not registered", and
  a registration under our name pointing at the wrong binary is repaired
  (remove + re-add) instead of reported "already"; harness subprocesses
  run with HOME/XDG_CONFIG_HOME set from the adapter's `home` so every
  adapter operates on the same root; bar widget hedges PATH for
  `~/.local/bin`; 13 new tests cover these plus setup/disconnect sweeps
  and the CLI exit-code contract.

- The Omarchy glove, first cut: `omnemo setup` installs the memory skill
  (copied to `~/.local/share/omnemo/skill/`, symlinked per harness dir —
  the live-box survey falsified the assumed propagation loop), the
  Quickshell bar widget (`omnemo.memory`, count + learned-today via
  `omnemo stats --json`), a boot warm-up user unit, and MCP registration
  for claude/codex (their own `mcp add`, read back via `mcp list`) and
  opencode/crush/gemini (atomic JSON config merge, read back from disk);
  pi is skill-only until its MCP surface is verified. `omnemo connect` /
  `disconnect [--all-pieces]` run the registration half alone. New core
  verbs: `stats --json`, `warm`. INSTALL.md (dual-audience) and
  `docs/omarchy-survey.md` (live 4.0.1 findings) added; per-adapter and
  glove test suites (38 new tests).

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
