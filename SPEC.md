# Omnemo v0.1 — Spec

*Draft 0.2 — 2026-08-28. Drafted by the build agent; architect review folded
in (four calls resolved — see Decisions). Build is greenlit.*

## One sentence

A memory-only MCP server plus an Omarchy-native integration layer, installable
by the user **or by their agent**, giving every harness on an Omarchy machine
one shared, human-like memory.

## Non-goals (read these first)

- **Not competing with Omarchy or any harness.** We fill their declared gap
  (their manual ships ten harnesses and zero memory) using only their public
  extension points.
- **Not a Mnemo Cortex port.** Mnemo's OS layer (boot, lanes, filing, wiki,
  user modelling) stays home. Omnemo is just the memory, rebuilt clean.
- **No cloud, no accounts, no telemetry.** Local-first; the store lives in
  the user's XDG data dir.

## Architecture

Two packages, one repo:

```
omnemo-core     — MCP server: save / recall / search / forget
                  SQLite + embeddings; composite recall ranking
                  (similarity + recency + category importance) and
                  category-aware decay. systemd user service.
omnemo-omarchy  — the glove: skill folder, shell plugin (bar widget),
                  hooks, harness registration. Depends on core.
```

### The memory core (clean-room build)

Built greenfield from this spec under the clean-room rules — no code copied
from Mnemo, designed fresh with lessons from Mnemo's production use as
requirements. Scope: the four memory verbs, ranking, decay. Nothing else.

**Decision — embeddings: LOCAL-FIRST, single path (resolved in review).**
A local embedded model, warmed at boot by the systemd unit so cold start is
a non-issue. The earlier "hybrid" idea — auto-discovering a provider key from
the harness environment — is **rejected**: it would silently send memory text
to a third party the user never authorized for that purpose, spend their API
quota, and fragment the vector space across embedders (breaking cross-harness
recall, success criterion #2). Bring-your-own-key becomes an **explicit
opt-in** (user sets `OMNEMO_EMBED_*` themselves) considered for v0.2+ —
never auto-discovered. One embedder per store, recorded in the store's
metadata.

**Recall tuning:** thresholds and ranking weights ship as exposed defaults,
never hard-coded constants — tuned on real recall data after release
(upstream lesson: measurement moved a predicted threshold by 3–5x).

### The Omarchy glove — four integrations, all on their rails

| Piece | Omarchy mechanism | What it does |
|---|---|---|
| Memory skill | `ln -sfn` into each harness skill dir (`~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`, `~/.pi/agent/skills`) — Omarchy's own per-dir idiom; **there is no automatic propagation loop** (falsified on the live box, see `docs/omarchy-survey.md`) | Teaches every harness when to save and when to recall — **conservative by default**: save decisions, lessons, durable facts, things that change a future answer; skip transient state, one-off mentions, anything re-derivable. Ships with explicit do-NOT-save examples — negative examples do the real work; over-saving is the #1 recall killer |
| Bar widget | Quickshell (QML) plugin in `~/.config/omarchy/plugins/omnemo.memory/` — `manifest.json` + `BarWidget.qml`, hot-reload, survives updates (the bar is `omarchy-shell`/Quickshell, **not waybar** — see survey) | Memory count · last recall · "learned today" |
| Boot + service | systemd user unit + `post-boot.d` hook | Server always up, embedder pre-warmed; optional morning digest — **stats only** (memory count, learned-today, last recall) straight from the store, no LLM pass. Synthesis/"dreaming" is deliberately out until v0.2+, as opt-in |
| Crash memory | Their `omarchy-agent-crash` → skill pattern | Skill addendum: recall prior crashes of the same binary before diagnosing |

**Harness registration:** `omnemo connect` detects installed harnesses
(claude / codex / opencode / …) and registers the MCP server with each one's
config. Idempotent; re-run any time. `omnemo disconnect` reverses it.
Each harness config format is its own small adapter **with its own test** —
never one shared assumption. After every write, connect **reads the config
back and verifies the harness sees the server**: a registration that can't
be read back is reported as a failure, never assumed. This is where
cross-harness installs silently half-work; we refuse to.

**Isolation:** an Omnemo store is **one human's memory**, shared across
their harnesses — that sharing is the feature, and single-user is a hard
guarantee. No multi-user mode. (Cross-user memory pollution is the
category's worst failure class; we exclude it by construction.)

## Install story (the demo IS the product)

1. `pipx install omnemo` *(AUR: `omnemo` — stretch goal for v0.1)*
2. `omnemo setup` — one command: service, skill symlink, plugin, hooks,
   `connect` on every harness found.
3. Or the Omarchy way: tell your agent **"Install Omnemo — follow
   INSTALL.md."** INSTALL.md is written for both audiences, human and agent
   (pattern proven in Mnemo Cortex).

## Success criteria (v0.1 ships when)

- [ ] Fresh Omarchy VM: agent-driven install completes from one sentence.
- [ ] A fact saved in Claude Code is recalled by OpenCode (cross-harness).
- [ ] `omarchy update` breaks nothing (all pieces in user-owned dirs).
- [ ] Crash demo: second crash of the same binary surfaces the first.
- [ ] Bar widget renders in default + one other theme.
- [ ] **Forget forgets**: a forgotten fact does not resurface in recall AND
      is gone from the store — deleted, not just deranked. (Forget is where
      memory products earn or lose trust.)
- [ ] `omnemo connect` read-back verification passes per harness adapter.

## Decisions (review resolved 2026-08-28)

1. **Embeddings**: local-first, single path; BYOK explicit opt-in v0.2+,
   never auto-discovered (see Architecture — the draft's hybrid lean was
   reversed in review, for the reasons recorded there).
2. **Auto-save**: conservative default with explicit do-not-save examples
   (see the skill row).
3. **Dream/synthesis**: hard-parked to v0.2+ opt-in; morning digest is
   stats-only in v0.1.
4. **Versioning**: independent semver + own CHANGELOG from day one; never
   coupled to Mnemo Cortex.

## Test bed

Omarchy in a VM (or a spare box). Never developed against a live production
Mnemo install; tested only in disposable environments.
