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

Every step reports what it did; nothing stops the remaining steps.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path

from .harnesses import HarnessResult, connect_all, disconnect_all

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
                    "enable it manually after next login"
                )
                break
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            lines.append(f"warm-up: systemctl unavailable ({e}) — unit written, not enabled")
            break
    else:
        lines.append("warm-up: service enabled and started")
    return lines


def setup(home: Path | None = None) -> tuple[list[str], list[HarnessResult]]:
    home = home or Path.home()
    lines: list[str] = []
    for step in (install_skill, install_plugin, install_warm_unit):
        try:
            lines.extend(step(home))
        except Exception as e:  # report, keep going — partial setup must be visible
            lines.append(f"{step.__name__}: FAILED — {e!r}")
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
