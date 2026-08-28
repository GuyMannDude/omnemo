# Omnemo — memory for Omarchy

**One shared memory for every agent harness on the box.**

Omarchy made coding agents system citizens. Omnemo gives them the one thing
they still wake up without: memory. Claude Code remembers what Codex did
yesterday. Your agent knows this app crashed before — and what fixed it.

Built just for [Omarchy](https://omarchy.org). Not a fork, not a patch — a
glove-fit layer made entirely from Omarchy's own extension points (skills,
user plugins, hooks), so it survives every `omarchy update`.

## What you get

- **Shared recall across all harnesses** — one memory store, spoken over MCP,
  registered with every agent CLI Omarchy ships. Save in one, recall in any.
- **Human-like memory, not a fixed database** — recall blends similarity,
  recency, and importance; memories decay at different rates by kind, the way
  yours do.
- **A memory skill** dropped into `~/.agents/skills/` — every harness learns
  *when* to remember and *when* to recall, automatically.
- **Crashes with a past** — Omarchy hands core dumps to your agent; Omnemo
  lets the agent answer "this crashed before, here's what fixed it."
- **Memory in the bar** — an Omarchy shell plugin showing what your machine
  remembered today.

## Install

> Fastest path: open your agent (`omarchy agent`) and say
> **"Install Omnemo — follow INSTALL.md."** It will do the rest.

Manual instructions: `INSTALL.md` *(coming with v0.1)*.

## Status

**Spec stage.** See [`SPEC.md`](./SPEC.md) for the v0.1 design. Watch this
repo — first release is in the works.

## Lineage

Omnemo is the memory core of [Mnemo Cortex](https://github.com/GuyMannDude/mnemo-cortex)
— "memory that works more like a human than the others" — rebuilt clean and
cut down to just memory, then fitted to Omarchy natively. MIT licensed, like
Omarchy itself.
