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

Your harness may also keep its own private memory. Use Omnemo for anything
another agent on this machine would need; keeping your own copy too is fine.
A fact that lives only in one harness's private memory is invisible to every
other agent.

## When to RECALL

- Before starting non-trivial work on this machine — one `recall` with a
  short description of the task. Cheap, often decisive.
- When the user references past work ("like last time", "the usual way",
  "what we decided about X").
- Before diagnosing a crash or recurring error: recall the binary or error
  first — this machine may have seen it before and stored the fix.

Recall returns ranked matches (similarity + recency + importance). Treat
results as leads, not gospel: they reflect what was true when saved.

**A new store.** If recall comes back empty or nearly so, this machine is new
to you. Early on, notice the few things about the user that change every
future answer — how much detail they want, how they like answers given — and
save them. Don't quiz them; if it isn't clear, ask once.

## When to SAVE — conservative by default

Save things that would change a future session's answer:

- **Decisions with a why** — "chose X over Y because Z".
- **Lessons paid for** — a root cause found, a fix that worked, a trap hit.
- **Durable facts about this machine or its people** — preferences the user
  stated, quirks of the hardware, project conventions not written elsewhere.
- **Choices the user made about this machine** — a setting changed, a default
  app picked, a feature turned off. Don't save the setting; save that the user
  chose it and why. The config file shows what is set, not that it was on
  purpose — without the memory, the next agent may "fix" it back.

One memory = one fact, in one or two plain sentences, with enough context to
stand alone months from now. Name concrete things (paths, versions, project
names) — future recall queries will match on them.

**Tell the user.** When you save something about the user or their choices,
say so in one plain sentence ("I'll remember you want the screen to stay on
for an hour."). They can't see the store; telling them is how they learn it
remembers — and how they catch it when it's wrong.

## Do NOT save (this list does the real work)

Over-saving is the #1 recall killer: every junk memory competes with a good
one in every future recall. Skip:

- **Transient state** — "the build is currently failing", "server is up",
  today's TODO. It will be false soon, and recalled anyway. (One exception:
  the single "where we left off" note — see Session bookends.)
- **One-off mentions** — a file you touched once, a command's routine output,
  a value you looked up and used.
- **Anything re-derivable** — code structure, git history, what a config
  file says. The next agent can read those directly; the repo is not going
  anywhere. (Why the user set it is not re-derivable — see "Choices the user
  made" above.)
- **Whole transcripts or long dumps** — save the conclusion, not the journey.
- **Secrets** — never API keys, passwords, tokens, or private credentials.
  If the fact is "where a credential lives", save the location, never the value.
- **Private details the user didn't ask you to keep** — health, money, family
  matters. This store is shared by every agent on the machine; when in doubt,
  ask before saving.

Rule of thumb: if you would not write it on a sticky note for a colleague
taking over tomorrow, do not save it.

## Session bookends

A light rhythm so the next session — yours or another agent's — picks up
where this one stopped.

**Open.** Before the first real task, `search` "where we left off" (add the
project name if the work belongs to one) — a literal match, so the note is
found every time — then `recall` the task itself. If a left-off note comes
back, start from it.

**Close** — when the user wraps up, or a big piece of work lands:

1. Save any decisions-with-why from the session that aren't saved yet.
2. Keep exactly ONE "where we left off" note per project — or one for the
   whole machine if the work isn't tied to a project. `search` for the
   current one, then save the new note with `supersedes=[its id]` so recall
   serves only the latest. If there is no current note yet, just save the
   new one. Start it with the words "Where we left off", save it as category
   `fact` (not `transient`, which ranks too low to be found), and keep it to
   two or three sentences: what landed, what is next, what is waiting on
   the user.

This note is the one allowed exception to the transient-state rule: it is
meant to go stale, and replacing it each time keeps exactly one copy alive.

## Crash memory

When Omarchy hands you a crash to diagnose (`omarchy-agent-crash`), FIRST
`recall` the crashing binary's name. If a prior crash of the same binary was
saved, lead with what fixed it last time. After diagnosing a NEW crash to a
root cause, save one memory: binary, symptom, root cause, fix.

## Forget

When the user says a saved fact is wrong or asks to remove it: `search` for
it, confirm the id, `forget <id>`. Forget deletes — it does not archive.
Tell the user what was deleted.
