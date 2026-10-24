# Omnemo — memory for Omarchy

> **Status (2026-10-23): active again.** Omnemo now has its dedicated Omarchy box (a Latitude on Omarchy 4.0.6); the agent-driven install was verified there on 2026-10-23, all five INSTALL steps: package, setup, save/recall, a fresh harness session recalling through the MCP server, and the bar widget. MIT, fork freely.

> *Agents come and go. The memory abides.*

**One shared memory for every agent harness on the box.**

Omarchy made coding agents system citizens. Omnemo gives them the one thing
they still wake up without: memory. Claude Code remembers what Codex did
yesterday. Your agent knows this app crashed before — and what fixed it.

Built just for [Omarchy](https://omarchy.org). Not a fork, not a patch — a
glove-fit layer made entirely from Omarchy's own extension points (skills,
user plugins, hooks), so it survives every `omarchy update`.

## What you get

- **Shared recall across harnesses** — one memory store, spoken over MCP,
  registered with Claude Code, Codex, OpenCode, Crush and Gemini (Pi gets the
  skill; its MCP registration is not supported yet). Save in one, recall in any.
- **Human-like memory, not a fixed database** — recall blends similarity,
  recency, and importance; memories decay at different rates by kind, the way
  yours do.
- **A memory skill** dropped into `~/.agents/skills/` and linked into the
  Claude Code, Codex and Pi skill dirs — those harnesses learn *when* to
  remember and *when* to recall, automatically.
- **Crashes with a past** — Omarchy hands core dumps to your agent; Omnemo
  lets the agent answer "this crashed before, here's what fixed it."
- **Memory in the bar** — an Omarchy shell plugin showing what your machine
  remembered today.

## Install

> Fastest path: pick a default agent if you haven't
> (`omarchy default agent claude`, or `codex`, …), open it (`omarchy agent`)
> and say **"Install Omnemo — follow INSTALL.md."** It will do the rest.

Manual instructions: [`INSTALL.md`](./INSTALL.md).

## Prove it

Memory is durable the instant a save returns — a crashing harness loses
nothing. Don't take our word for it:

```sh
python3 examples/crash_demo.py
```

It opens a real MCP session against `omnemo serve`, saves a memory, SIGKILLs
the server the moment the save is acknowledged (no shutdown, no flush), then
recalls the memory from a fresh process.

### Cross-harness recall, live

The core promise — save in one harness, recall in any — is a two-command
demo on a box with two authenticated harnesses:

```sh
# Ask Claude Code (Anthropic) to remember something
claude -p 'Use the omnemo save tool to store this memory: the electronics
repair shop favorite song was "Everything'\''s Broken" by Bob Dylan' \
  --allowedTools "mcp__omnemo__save"

# Ask Codex (OpenAI) — a different vendor's harness, fresh process
codex exec 'Using only the omnemo MCP recall tool: what was the favorite
song at the electronics repair shop?'
```

Run live on the reference Omarchy 4.0.1 box:

```
mcp: omnemo/recall started
mcp: omnemo/recall (completed)
codex
"Everything's Broken" by Bob Dylan.
```

One memory, written by one vendor's agent, recalled by its competitor.
The memory belongs to the machine, not the harness.

## Status

**v0.2.0, proven on a clean Omarchy 4.0.1 box (September 2026); partly
re-verified on a clean Omarchy 4.0.4 box (2026-10-09).** Fresh install to green
in minutes: MCP registered with all five supported harnesses (verified
read-back, not just name-matched), skill linked, bar widget live.

Re-proven on 4.0.4: the manual INSTALL walk, crash-durable save
(`examples/crash_demo.py`), the skill surviving repeated `omarchy update` runs,
theme switches and shell restarts, the bar plugin on the 4.0.4 Quickshell bar,
and local-first operation with the network cut.

Proven on 4.0.1 only, not yet re-run on 4.0.4: the agent-driven install
("Install Omnemo — follow INSTALL.md"), save-in-one-harness / recall-in-another,
and survival of harness upgrades. The crash-diagnosis hook is a real 4.0.4
extension point; no agent was driven through a crash. OpenCode, Crush and
Gemini are registered but were not driven. See [`SPEC.md`](./SPEC.md) for the
design.

## Lineage

Omnemo is the memory core of [Mnemo Cortex](https://github.com/GuyMannDude/mnemo-cortex)
— "memory that works more like a human than the others" — rebuilt clean and
cut down to just memory, then fitted to Omarchy natively. MIT licensed, like
Omarchy itself.
