# Omnemo v0.1 — Spec

*Draft 0.1 — 2026-08-28. Author: CC. Review: Opie. Owner: Guy.*

## One sentence

A memory-only MCP server plus an Omarchy-native integration layer, installable
by the user **or by their agent**, giving every harness on an Omarchy machine
one shared, human-like memory.

## Non-goals (read these first)

- **Not competing with Omarchy or any harness.** We fill their declared gap
  (their manual ships ten harnesses and zero memory) using only their public
  extension points.
- **Not a Mnemo Cortex port.** Mnemo's OS layer (boot, lanes, filing, wiki,
  user modelling) stays home. Omnemo is the memory 46%, rebuilt clean.
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
from live Mnemo, designed fresh with five months of Mnemo failure data as
requirements. Scope: the four memory verbs, ranking, decay. Nothing else.

**Open question #1 — embeddings (decides everything downstream):**
- (a) Local model via a small embedded runtime — zero-config, private, slower
  cold start; or
- (b) bring-your-own-key — better vectors, but "seamless" dies at the key
  prompt; or
- (c) **hybrid (leaning)**: local by default, upgrade path if a key exists in
  the environment. Agents on Omarchy already have provider keys configured —
  the harness's own key may be discoverable without asking the user anything.

### The Omarchy glove — four integrations, all on their rails

| Piece | Omarchy mechanism | What it does |
|---|---|---|
| Memory skill | `~/.agents/skills/omnemo/` (their symlink loop feeds all five harness skill dirs) | Teaches every harness when to save and when to recall |
| Bar widget | User shell plugin in `~/.config/omarchy/plugins/` (hot-reload, survives updates) | Memory count · last recall · "learned today" |
| Boot + service | systemd user unit + `post-boot.d` hook | Server always up; optional morning "what I remember" notification |
| Crash memory | Their `omarchy-agent-crash` → skill pattern | Skill addendum: recall prior crashes of the same binary before diagnosing |

**Harness registration:** `omnemo connect` detects installed harnesses
(claude / codex / opencode / …) and registers the MCP server with each one's
config. Idempotent; re-run any time. `omnemo disconnect` reverses it.

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

## Open questions for review

1. Embeddings (above — the big one).
2. Skill wording: how aggressive should auto-save guidance be? (Over-saving
   pollutes recall; Mnemo's lesson.)
3. Dream/synthesis layer: v0.1 says **no** (memory only), but the morning
   notification wants a daily digest eventually. Park or scope?
4. Versioning: independent of Mnemo Cortex (this is a separate product with
   its own CHANGELOG from day one).

## Test bed

Omarchy in a VM on IGOR-2 (or a spare box). Never developed against live
Mnemo; never touches Rocky.
