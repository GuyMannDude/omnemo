# Omarchy 4.0.1 extension-point survey (live VM, 2026-08-28)

Probed on a fresh Omarchy 4.0.1 install (QEMU VM, IGOR `~/omnemo-lab/`).
Every claim below was read from the running system, not from docs.
Re-verify against the target release before each Omnemo release.

## Harnesses present on a fresh install

Six agent CLIs ship installed: `claude`, `codex`, `opencode`, `crush`,
`gemini`, `pi`. On our test box `gemini` was **broken out of the box**
(mise npm install failure in node-pty) — `connect` must treat a present-but-
broken harness as skip-with-report, never as fatal.

## Skills — there is NO automatic symlink loop

**Spec draft assumed dropping a folder in `~/.agents/skills/` propagates to
every harness. It does not.** Omarchy's own provisioning/migrations link each
skill explicitly into each harness dir:

```
~/.agents/skills/          # convention dir (agents' shared home)
~/.claude/skills/          # Claude Code
~/.codex/skills/           # Codex
~/.pi/agent/skills/        # pi
```

(from `/usr/share/omarchy/migrations/1786098807.sh` + `1786539345.sh`:
`ln -sfn "$OMARCHY_PATH/default/agents/skills/<skill>" <dir>/<skill>` per dir.)

opencode, crush, gemini had **no skills dir** on the fresh box.
→ Omnemo `setup` must do its own per-dir `ln -sfn`, same idiom.

## The bar is Quickshell (QML), not waybar

No `~/.config/waybar/`. The bar, notifications, overlays all live in one
Quickshell process, `omarchy-shell`. Docs on the box:
`/usr/share/omarchy/shell/plugins/README.md`, `bar/README.md`,
and the agent-facing `plugins.md` inside the `omarchy` skill.

- User plugins: `~/.config/omarchy/plugins/<plugin-id>/` — hot-reload,
  survives `omarchy update` (user-owned dir).
- A bar widget = plugin with `manifest.json` (`schemaVersion: 1`,
  `kinds: ["bar-widget"]`, `entryPoints.barWidget: "BarWidget.qml"`) plus a
  QML file: `BarWidget { moduleName: "<id>" }` importing `qs.Commons`/`qs.Ui`.
- Enable/inspect: `omarchy plugin list|enable|disable`; layout in
  `~/.config/omarchy/shell.json` (hot-reloads on save).
- First-party specimens copied to `~/omnemo-lab/omarchy-ref/` (clock,
  tailscale) — pattern source for the Omnemo widget.

## MCP registration per harness (fresh-box findings)

| Harness | Mechanism found | Read-back path |
|---|---|---|
| claude | `claude mcp add` CLI exists | `claude mcp get/list` |
| codex | `codex mcp add <name> -- <cmd>` CLI exists | `codex mcp list` |
| opencode | `opencode mcp add` exists (interactivity unverified); config `~/.config/opencode/opencode.json` present on fresh box | parse config file |
| crush | no `mcp` subcommand in `--help`; config file (`~/.config/crush/crush.json`) did not exist on fresh box | parse config file |
| gemini | CLI broken on fresh box (mise/node-pty build failure) | n/a — skip-with-report specimen |
| pi | extension system (`pi install <source>`); MCP support unverified | TBD |

## Hooks

`~/.config/omarchy/hooks/` exists on the fresh box with subdirs:
`battery-low.d  font-set.d  post-boot.d  post-update.d
pre-refresh-pacman.d  theme-set.d`.

## Misc

- `omarchy-agent-crash` exists in `/usr/share/omarchy/bin/` (crash-memory
  integration point, per spec).
- Fresh install: user account `sparks`, no harness ever launched — most
  harness config files do not exist until first run or first write.
