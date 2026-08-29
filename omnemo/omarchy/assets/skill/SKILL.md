---
name: omnemo
description: Shared memory for every agent on this machine. Use to RECALL relevant context before starting non-trivial work, and to SAVE decisions, lessons, and durable facts other sessions (or other agents) will need. One store, all harnesses — what Codex saves, Claude recalls.
---

# Omnemo — the machine's shared memory

This box runs one memory store, shared by every agent harness on it. It is
served over MCP as `omnemo` (tools: `save`, `recall`, `search`, `forget`).
If the MCP tools are unavailable, the same verbs work from the shell:
`omnemo save "..."`, `omnemo recall "..."`, `omnemo search "..."`,
`omnemo forget <id>`, `omnemo stats`.

## When to RECALL

- Before starting non-trivial work on this machine — one `recall` with a
  short description of the task. Cheap, often decisive.
- When the user references past work ("like last time", "the usual way",
  "what we decided about X").
- Before diagnosing a crash or recurring error: recall the binary or error
  first — this machine may have seen it before and stored the fix.

Recall returns ranked matches (similarity + recency + importance). Treat
results as leads, not gospel: they reflect what was true when saved.

## When to SAVE — conservative by default

Save things that would change a future session's answer:

- **Decisions with a why** — "chose X over Y because Z".
- **Lessons paid for** — a root cause found, a fix that worked, a trap hit.
- **Durable facts about this machine or its people** — preferences the user
  stated, quirks of the hardware, project conventions not written elsewhere.

One memory = one fact, in one or two plain sentences, with enough context to
stand alone months from now. Name concrete things (paths, versions, project
names) — future recall queries will match on them.

## Do NOT save (this list does the real work)

Over-saving is the #1 recall killer: every junk memory competes with a good
one in every future recall. Skip:

- **Transient state** — "the build is currently failing", "server is up",
  today's TODO. It will be false soon, and recalled anyway.
- **One-off mentions** — a file you touched once, a command's routine output,
  a value you looked up and used.
- **Anything re-derivable** — code structure, git history, contents of
  config files. The next agent can read those directly; the repo is not
  going anywhere.
- **Whole transcripts or long dumps** — save the conclusion, not the journey.
- **Secrets** — never API keys, passwords, tokens, or private credentials.
  If the fact is "where a credential lives", save the location, never the value.

Rule of thumb: if you would not write it on a sticky note for a colleague
taking over tomorrow, do not save it.

## Crash memory

When Omarchy hands you a crash to diagnose (`omarchy-agent-crash`), FIRST
`recall` the crashing binary's name. If a prior crash of the same binary was
saved, lead with what fixed it last time. After diagnosing a NEW crash to a
root cause, save one memory: binary, symptom, root cause, fix.

## Forget

When the user says a saved fact is wrong or asks to remove it: `search` for
it, confirm the id, `forget <id>`. Forget deletes — it does not archive.
Tell the user what was deleted.
