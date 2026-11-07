"""`omnemo setup` — put every glove piece in place, idempotently.

Pieces (SPEC.md "The Omarchy glove", mechanisms verified in
docs/omarchy-survey.md):

1. Memory skill  → copy packaged skill to ~/.local/share/omnemo/skill/,
                   then `ln -sfn` into each harness skill dir (Omarchy's own
                   per-dir idiom — there is no automatic propagation loop).
2. Bar widget    → copy packaged Quickshell plugin to
                   ~/.config/omarchy/plugins/omnemo.memory/ (hot-reloaded).
3. Warm-up       → systemd user oneshot that pre-loads the embedder at boot.
4. Harnesses     → connect_all() MCP registration with read-back verify.
5. Bar (opt-in)  → `setup --bar` / `omnemo bar on|off`: a spot for the
                   widget in the bar layout (~/.config/omarchy/shell.json,
                   hot-reloaded). Plain `setup` leaves the layout alone (#1).

Every step reports what it did; nothing stops the remaining steps.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path

from .harnesses import (
    HarnessResult,
    _merge_json_key,
    _read_json_key,
    connect_all,
    disconnect_all,
)

# The dirs Omarchy's own provisioning links skills into (survey).
SKILL_LINK_DIRS = [
    ".agents/skills",
    ".claude/skills",
    ".codex/skills",
    ".pi/agent/skills",
]

SKILL_NAME = "omnemo"
PLUGIN_ID = "omnemo.memory"
UNIT_NAME = "omnemo-warm.service"
SHELL_JSON = ".config/omarchy/shell.json"
BAR_SECTION = "right"


def _copy_asset_tree(asset: str, dest: Path) -> None:
    """Copy a packaged asset directory onto dest (overwrite, no deletes)."""
    _copy_entry_tree(resources.files("omnemo.omarchy") / "assets" / asset, dest)


def _copy_entry_tree(src, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        target = dest / entry.name
        if entry.is_dir():
            _copy_entry_tree(entry, target)
        else:
            target.write_bytes(entry.read_bytes())


def install_skill(home: Path) -> list[str]:
    """Copy the skill into a stable home and link it everywhere. Returns
    human-readable report lines."""
    lines = []
    skill_home = home / ".local/share/omnemo/skill"
    _copy_asset_tree("skill", skill_home)
    lines.append(f"skill: installed at {skill_home}")
    for rel in SKILL_LINK_DIRS:
        d = home / rel
        d.mkdir(parents=True, exist_ok=True)
        link = d / SKILL_NAME
        if link.is_symlink() or link.exists():
            if link.is_symlink() and link.resolve() == skill_home.resolve():
                lines.append(f"skill: {link} already linked")
                continue
            lines.append(f"skill: {link} exists and is not ours — LEFT ALONE")
            continue
        link.symlink_to(skill_home)
        lines.append(f"skill: linked {link}")
    return lines


def install_plugin(home: Path) -> list[str]:
    dest = home / ".config/omarchy/plugins" / PLUGIN_ID
    _copy_asset_tree("plugin", dest)
    return [f"plugin: installed at {dest} (omarchy-shell hot-reloads)"]


def install_warm_unit(home: Path, enable: bool = True) -> list[str]:
    lines = []
    unit_dir = home / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    src = resources.files("omnemo.omarchy") / "assets/systemd" / UNIT_NAME
    (unit_dir / UNIT_NAME).write_text(src.read_text())
    lines.append(f"warm-up: unit written to {unit_dir / UNIT_NAME}")
    if not enable:
        return lines
    for argv in (
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", UNIT_NAME],
    ):
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                lines.append(
                    f"warm-up: `{' '.join(argv)}` exited {proc.returncode} "
                    f"({(proc.stderr or proc.stdout).strip()[:120]}) — "
                    f"run after next login: systemctl --user enable --now {UNIT_NAME}"
                )
                break
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            lines.append(f"warm-up: systemctl unavailable ({e}) — unit written, not enabled")
            break
    else:
        lines.append("warm-up: service enabled and started")
    return lines


def _is_ours(entry) -> bool:
    """A layout entry is a bare id (Omarchy 4.5 boxes) or an object with an
    id (stock shell.json on master); both forms are on real machines."""
    return entry == PLUGIN_ID or (isinstance(entry, dict) and entry.get("id") == PLUGIN_ID)


def _bar_layout(home: Path) -> tuple[Path, dict | None]:
    path = home / SHELL_JSON
    layout = _read_json_key(path, ["bar", "layout"])
    if layout is not None and not isinstance(layout, dict):
        raise ValueError(f"{path}: bar.layout is not an object")
    return path, layout


def _section_with_widget(layout: dict) -> str | None:
    for section, entries in layout.items():
        if isinstance(entries, list) and any(_is_ours(e) for e in entries):
            return section
    return None


def bar_on(home: Path) -> list[str]:
    """Give the widget a spot in the bar layout (the plugin files are
    install_plugin's job). Idempotent: already on the bar means no write."""
    path, layout = _bar_layout(home)
    if layout is None:
        raise RuntimeError(
            f"no bar layout in {path} yet — run "
            f"`omarchy bar move {PLUGIN_ID} --section {BAR_SECTION}` once "
            "from your desktop session (it writes the full layout)"
        )
    section = _section_with_widget(layout)
    if section:
        lines = [f"bar: {PLUGIN_ID} already on the bar ({section})"]
    else:
        # Mirror the file's own entry form so the shell keeps reading it.
        objects = any(
            isinstance(e, dict)
            for entries in layout.values() if isinstance(entries, list)
            for e in entries
        )
        layout.setdefault(BAR_SECTION, []).append(
            {"id": PLUGIN_ID} if objects else PLUGIN_ID
        )
        _merge_json_key(path, ["bar", "layout"], layout)
        lines = [f"bar: {PLUGIN_ID} added to the {BAR_SECTION} section of {path} (hot-reloads)"]
    disabled = _read_json_key(path, ["disabledPlugins"])
    if isinstance(disabled, list) and PLUGIN_ID in disabled:
        _merge_json_key(path, ["disabledPlugins"], [p for p in disabled if p != PLUGIN_ID])
        lines.append(f"bar: {PLUGIN_ID} re-enabled (an earlier `omarchy plugin disable` had it off)")
    return lines


def bar_off(home: Path) -> list[str]:
    """Take the widget off the bar. Not there (or no layout at all) is fine."""
    path, layout = _bar_layout(home)
    if layout is None:
        return [f"bar: {PLUGIN_ID} not on the bar (no layout in {path})"]
    kept = {
        section: [e for e in entries if not _is_ours(e)] if isinstance(entries, list) else entries
        for section, entries in layout.items()
    }
    if kept == layout:
        return [f"bar: {PLUGIN_ID} not on the bar"]
    _merge_json_key(path, ["bar", "layout"], kept)
    return [f"bar: {PLUGIN_ID} removed from {path} (hot-reloads)"]


def setup(home: Path | None = None, bar: bool = False) -> tuple[list[str], list[HarnessResult]]:
    home = home or Path.home()
    lines: list[str] = []
    steps = [("skill", install_skill), ("plugin", install_plugin), ("warm-up", install_warm_unit)]
    if bar:
        steps.append(("bar", bar_on))
    for name, step in steps:
        try:
            lines.extend(step(home))
        except Exception as e:  # report, keep going — partial setup must be visible
            lines.append(f"[fail] {name}: {e!r}")
    results = connect_all(home=home)
    return lines, results


def teardown(home: Path | None = None) -> tuple[list[str], list[HarnessResult]]:
    """`omnemo disconnect --all-pieces` support: remove links, plugin, unit.
    The skill copy and the store are left in place (they are the user's)."""
    home = home or Path.home()
    lines: list[str] = []
    skill_home = home / ".local/share/omnemo/skill"
    for rel in SKILL_LINK_DIRS:
        link = home / rel / SKILL_NAME
        if link.is_symlink() and link.resolve() == skill_home.resolve():
            link.unlink()
            lines.append(f"skill: unlinked {link}")
    plugin_dir = home / ".config/omarchy/plugins" / PLUGIN_ID
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
        lines.append(f"plugin: removed {plugin_dir}")
    unit = home / ".config/systemd/user" / UNIT_NAME
    if unit.exists():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", UNIT_NAME],
            capture_output=True, timeout=30,
        )
        unit.unlink()
        lines.append(f"warm-up: removed {unit}")
    return lines, disconnect_all(home=home)
