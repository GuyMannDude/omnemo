# Omnemo v0.2 — Rituals (draft roadmap)

*Direction set 2026-08-31. Everything here is **opt-in** — offered, never
burnt in. A user who wants bare save/recall keeps exactly that. Max options,
zero ceremony imposed.*

## The idea

v0.1 gave agents a memory. v0.2 gives them **work habits** — the rituals
that turn "an agent with recall" into "a colleague who shows up prepared."
Each ritual is a small module the user enables (or doesn't) at install or
any time after:

```
omnemo rituals enable boot
omnemo rituals enable close
omnemo rituals enable watch
omnemo rituals disable <any>
```

## 1. Boot ritual (`boot`)

The agent starts every session knowing where things stand: what happened
last session, open threads, anything a watch routine flagged overnight.
Delivered as a skill so every harness runs it the same way — the agent's
first act is a recall of the standing kickstart note plus recent
high-signal memories.

## 2. Close ritual (`close`)

The mirror of boot: at session end the agent writes tomorrow's kickstart —
what was decided, what's unfinished, what tomorrow-me needs first. Saved as
a dedicated memory kind (`kickstart`) that boot recall surfaces first and
that each new close replaces rather than stacks.

Boot + close pair into a loop: every session begins where the last one
actually ended, in any harness (the kickstart written by Claude Code greets
Codex just the same — one memory, shared habits).

## 3. Watch routines (`watch`)

The generalizable primitive behind our own security watcher: **a scheduled
job that writes findings into memory**, so the agent wakes up informed
without the user relaying news. Ships as a systemd user timer writing
`watch`-kind memories that the boot ritual surfaces.

First watchers, each individually opt-in:
- **updates** — harness/package versions drifted, `omarchy update`
  available.
- **crashes** — recurrence summary built on the v0.1 crash-memory hook
  ("this binary crashed 3× this week").
- **security** — advisories touching installed harnesses/runtimes
  (scope carefully; start with version-lag, not CVE feeds).

## Explicitly NOT in v0.2

- **Agent-to-agent messaging (a bus)** — needs a multi-agent household to
  be worth its weight; demand-gated on real users asking for handoff.
- **Task board / lanes / supervision** — same gate.

## Design rules

1. **Opt-in forever.** No ritual ever becomes required for core
   save/recall. Uninstalling a ritual leaves memories intact.
2. **Glove rules apply** — rituals use only public extension points
   (skills, systemd user units, hooks); everything survives
   `omarchy update`.
3. **One memory, shared habits** — rituals are harness-agnostic skills;
   no per-harness behavior forks.
