# Omnemo Changelog

## Unreleased

- INSTALL/Uninstall: `omarchy plugin disable omnemo.memory` first, because
  `disconnect --all-pieces` removes the widget's files but leaves its spot
  in the bar layout (`~/.config/omarchy/shell.json`). Found on the gate-1
  wipe, 2026-10-24. Words only; a `disconnect` that does it itself is a
  post-release candidate.
- INSTALL: Gemini lists the server as `Disabled` until the folder is
  trusted (Gemini 0.65 folder trust, not a registration fault). Found on
  the gate-1 run, 2026-10-24; one explanatory line at step 2.
- **INSTALL: three things the first zero-fix stranger run tripped on**
  (gate-1 run on the 4.0.6 box, 2026-10-24): the pi setup row says
  `skipped — MCP registration not supported yet`, which the doc's list of
  ok rows did not name; step 4 must be run from a NEW agent session,
  because the session that ran setup (the installing agent itself) cannot
  see the new MCP server until it restarts; and the cross-harness check
  now says what to do when the second harness is missing or not logged
  in. Words only.
- **The documented update was a silent no-op.** Found on the first real
  update of the 4.0.6 box (2026-10-24): `pip install --upgrade git+…`
  resolved the new commit and installed nothing, because the version number
  had not changed, and `omnemo setup` then re-copied the OLD packaged skill
  with a fresh timestamp. The command reported success either way. Fixes:
  the version now moves ahead of a release (`0.2.1.dev1`, so main delivers),
  and INSTALL's "To update later" is two lines — the pip upgrade, then
  `omnemo setup`, since the skill, bar plugin and warm-up unit are copies —
  with a check that `omnemo --version` actually changed. No code change.
- **SKILL.md: when to act, not just what to save.** Day one on a real
  Omarchy 4.0.6 box with an empty store (2026-10-24): the save rules held,
  but the agent kept the user's basics in its own private memory and the
  shared store stayed near-empty. Wording only, no code change:
  a new-store paragraph (learn how the user wants answers, early, ask once);
  "choices the user made" (save that they chose a setting and why, not the
  setting); "tell the user" in one sentence when you save something about
  them; how Omnemo relates to a harness's private memory; a privacy bullet
  (health, money, family: ask before saving to a shared store); and
  **Session bookends** — open with a literal `search "where we left off"`,
  close by saving decisions and ONE rolling left-off note per project
  (category `fact`, superseding the previous one). The bookends were run
  live before shipping: a `transient` note ranks too low to be found, and
  `recall` ranks a multi-sentence note below older facts while `search`
  finds it every time — hence the literal phrase and the category.
- **INSTALL: a virtual environment is the default install.** Found on the
  first real Omarchy 4.0.6 box (2026-10-23): fresh Omarchy has no pipx, and
  installing it needs `sudo`, which an agent-driven install cannot answer.
  The agent fell back to `~/.local/share/omnemo-venv` with a symlink at
  `~/.local/bin/omnemo`; that path is now the documented default, with one
  update command. pipx stays as the human alternative. No code change.
- README: project resumed; the 2026-10-15 parked banner is gone.

## 0.2.0 — 2026-09-07

- **Truth changes are no longer invisible to recall.** Found by the Memory
  Proving Ground (S02, 2026-09-04): save "X is alive", then "X is
  decommissioned", ask "is X alive?" — the stale sentence came back first,
  with real embeddings. Two opt-in additions, core save/recall untouched:
  `save` now returns `near_duplicates` (live memories at/above
  `near_duplicate_similarity`, default 0.90, at most `near_duplicate_limit`)
  so the caller learns an older claim exists — the write still lands,
  nothing is held; and `save(..., supersedes=[ids])` marks those memories as
  replaced: `recall` never serves them, `search` lists them with
  `superseded_by`, and forgetting the superseder restores them. Unknown ids
  raise and write nothing. MCP `save` takes `supersedes` and returns
  `near_duplicates`; `search` reports `superseded_by`; CLI `save
  --supersedes ID...` and prints near-duplicates. Schema: `memories` gains
  `superseded_by` (migrated in place on first open of a 0.1.x store).
- **Breaking, mildly:** `Store.save` returns a `SaveResult` instead of a
  `Memory`. Every `Memory` field reads through (`.id`, `.category`,
  `.created_at`, …) so existing callers keep working; `.memory` is the row
  and `.near_duplicates` the signal. Superseding an already-superseded id
  raises. `near_duplicate_limit = 0` turns the write-time scan off.
  `stats()` gains `superseded`.

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
