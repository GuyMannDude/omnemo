# Installing Omnemo on Omarchy

Written for both audiences: a human at a terminal, or an agent told
*"Install Omnemo — follow INSTALL.md."* Every step ends with a check;
do not continue past a failed check — report it instead.

Requires: Omarchy 2.0+ (surveyed against 4.0.1, re-verified on 4.0.4, agent-driven install verified on 4.0.6), Python 3.11+.

## 1. Install the package

A plain virtual environment is the default: it needs no `sudo`, so an
agent can finish this step on a fresh box, and it gives updates one path.

```bash
python3 -m venv ~/.local/share/omnemo-venv
~/.local/share/omnemo-venv/bin/pip install git+https://github.com/GuyMannDude/omnemo
mkdir -p ~/.local/bin
ln -sf ~/.local/share/omnemo-venv/bin/omnemo ~/.local/bin/omnemo
```

Omarchy already puts `~/.local/bin` on `PATH`. To update later, two lines —
the package, then the copies it installs (the skill, the bar plugin and the
warm-up unit are copies made by `omnemo setup`; they stay old until it runs
again):

```bash
~/.local/share/omnemo-venv/bin/pip install --upgrade git+https://github.com/GuyMannDude/omnemo
omnemo setup
```

**Check:** `omnemo --version` shows a newer version than before. If it does
not, nothing was updated: pip reinstalls only when the version number changes
(every Omnemo release bumps it) and otherwise says "Requirement already
satisfied" instead of failing.

If you prefer pipx (a human at the terminal; fresh Omarchy ships without it
and installing it needs `sudo`): `sudo pacman -Syu --needed python-pipx`,
then `pipx install git+https://github.com/GuyMannDude/omnemo`. Pick one
method and stay with it; mixing the two leaves two `omnemo` binaries.

**Check:** `omnemo --version` prints a version.

## 2. Run setup

```bash
omnemo setup
```

One command, idempotent, safe to re-run. It:

- installs the **memory skill** and links it into these harness skill dirs
  (`~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`,
  `~/.pi/agent/skills`)
- installs the **bar widget** at `~/.config/omarchy/plugins/omnemo.memory/`
- writes and enables the **warm-up service** (`omnemo-warm.service`,
  systemd user unit — pre-loads the embedding model at login; the first
  run downloads the model, which can take a few minutes)
- **registers the MCP server** with each installed harness (claude, codex,
  opencode, crush, gemini) and **reads each registration back** — a row
  it could not verify is printed as `FAIL`, never assumed

**Check:** the summary lists each piece, and every harness row reads
`ok` (`registered`, `already`, `skipped — not installed`, or for pi
`skipped — MCP registration not supported yet (skill link only)`).
A `FAIL` row names what to fix; the other rows are still in effect.
Gemini note: `gemini mcp list` shows `omnemo … - Disabled` until you trust
the folder you run Gemini in (it asks on its first interactive launch
there). The registration is correct; trust turns it on.

## 3. Verify memory works end to end

```bash
omnemo save "Omnemo installed on this machine on $(date +%F)"
omnemo recall "when was omnemo installed"
omnemo stats
```

**Check:** recall returns the fact you just saved; stats shows
`memories: 1` (or more) and `learned today: ≥ 1`.

## 4. Verify a harness sees the server

Start a **new** session of your usual agent (e.g. `claude`) and ask it:
*"Use the omnemo MCP server to recall: when was omnemo installed?"*
A session that was already open when setup ran does not see the new
server until it restarts — that includes the agent doing this install.

**Check:** the agent calls the `recall` tool and reports the fact from
step 3. Cross-harness, if a *second* harness is installed **and logged
in**: ask it the same question — same answer, same store. With one
harness, or a second one that is not logged in, this step is complete
with the first check.

## 5. Show the bar widget (optional)

Third-party plugins are discovered but land **disabled** — enable ours,
then place it:

```bash
omarchy plugin enable omnemo.memory
omarchy bar move omnemo.memory --section right
```

(Run these inside the graphical session — they talk to the running
`omarchy-shell`.)

**Check:** the bar shows `𝍇 N` (your memory count). It refreshes every
minute; click it to refresh now.

## Uninstall

```bash
omarchy plugin disable omnemo.memory   # if you enabled the bar widget: frees its spot on the bar
omnemo disconnect --all-pieces   # unregister harnesses, remove links/plugin/unit
rm ~/.local/bin/omnemo && rm -rf ~/.local/share/omnemo-venv   # or: pipx uninstall omnemo
```

(`disconnect` removes the widget's files but not its place in the bar
layout; the first line does that, and is harmless if the widget was
never enabled.)

Your memory store (`~/.local/share/omnemo/`) is deliberately left in
place; delete it yourself if you want the memories gone.
