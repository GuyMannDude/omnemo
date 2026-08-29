"""Per-harness MCP registration adapters.

Each adapter registers the Omnemo MCP server with one agent harness and then
READS THE REGISTRATION BACK from the harness's own config surface. A write
that cannot be read back is reported as a failure, never assumed to have
worked — cross-harness installs silently half-work exactly here, and we
refuse to. (SPEC.md, "Harness registration".)

Two adapter shapes:
- CLI adapters (claude, codex): the harness owns its config format and ships
  an `mcp add` command; we call it and read back via `mcp list`.
- File adapters (opencode, crush, gemini): we merge one key into the
  harness's JSON config, atomically, touching nothing else, and read the
  file back.

Mechanisms were surveyed on a live Omarchy 4.0.1 box — docs/omarchy-survey.md.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SERVER_NAME = "omnemo"
SERVER_COMMAND = ["omnemo", "serve"]

# Injection point for tests: run(argv) -> (exit_code, stdout+stderr text).
Runner = Callable[[list[str]], tuple[int, str]]


def _default_runner(argv: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        return 127, f"{argv[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, f"{argv[0]}: timed out"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@dataclass
class HarnessResult:
    harness: str
    action: str  # "registered" | "already" | "removed" | "skipped" | "failed"
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.action in ("registered", "already", "removed", "skipped")


def _merge_json_key(path: Path, keys: list[str], value: dict) -> None:
    """Set config[keys[0]][keys[1]] = value in the JSON file at path,
    creating the file and parents as needed, preserving every other key.
    Atomic: write temp file, then rename."""
    data = {}
    if path.exists():
        data = json.loads(path.read_text() or "{}")
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a JSON object")
    node = data
    for key in keys[:-1]:
        nxt = node.get(key)
        if nxt is None:
            nxt = node[key] = {}
        elif not isinstance(nxt, dict):
            raise ValueError(f"{path}: '{key}' exists but is not an object")
        node = nxt
    node[keys[-1]] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".omnemo-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def _read_json_key(path: Path, keys: list[str]):
    if not path.exists():
        return None
    node = json.loads(path.read_text() or "{}")
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _remove_json_key(path: Path, keys: list[str]) -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text() or "{}")
    node = data
    for key in keys[:-1]:
        node = node.get(key)
        if not isinstance(node, dict):
            return False
    if keys[-1] not in node:
        return False
    del node[keys[-1]]
    tmp = path.with_suffix(path.suffix + ".omnemo-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)
    return True


class Harness:
    """Base: detection by CLI presence; connect/disconnect per subclass."""

    name: str = ""

    def __init__(self, home: Path | None = None, runner: Runner | None = None):
        self.home = home or Path.home()
        self.run = runner or _default_runner

    def detected(self) -> bool:
        return shutil.which(self.name) is not None

    def connect(self) -> HarnessResult:
        raise NotImplementedError

    def disconnect(self) -> HarnessResult:
        raise NotImplementedError


class _CliHarness(Harness):
    """Harness whose own CLI manages MCP config (claude, codex)."""

    add_argv: list[str] = []
    list_argv: list[str] = []
    remove_argv: list[str] = []

    def _registered(self) -> bool | None:
        """True/False from `mcp list` read-back; None if the CLI failed."""
        code, out = self.run(self.list_argv)
        if code != 0:
            return None
        return SERVER_NAME in out

    def connect(self) -> HarnessResult:
        if self._registered() is True:
            return HarnessResult(self.name, "already")
        code, out = self.run(self.add_argv)
        if code != 0:
            return HarnessResult(
                self.name, "failed", f"add exited {code}: {out.strip()[:200]}"
            )
        # Read-back: the registration must be visible to the harness itself.
        seen = self._registered()
        if seen is not True:
            return HarnessResult(
                self.name,
                "failed",
                "add succeeded but read-back could not see the server",
            )
        return HarnessResult(self.name, "registered")

    def disconnect(self) -> HarnessResult:
        if self._registered() is not True:
            return HarnessResult(self.name, "skipped", "was not registered")
        code, out = self.run(self.remove_argv)
        if code != 0:
            return HarnessResult(
                self.name, "failed", f"remove exited {code}: {out.strip()[:200]}"
            )
        if self._registered() is True:
            return HarnessResult(
                self.name, "failed", "remove succeeded but server still listed"
            )
        return HarnessResult(self.name, "removed")


class ClaudeHarness(_CliHarness):
    name = "claude"
    add_argv = ["claude", "mcp", "add", "--scope", "user",
                SERVER_NAME, "--"] + SERVER_COMMAND
    list_argv = ["claude", "mcp", "list"]
    remove_argv = ["claude", "mcp", "remove", "--scope", "user", SERVER_NAME]


class CodexHarness(_CliHarness):
    name = "codex"
    add_argv = ["codex", "mcp", "add", SERVER_NAME, "--"] + SERVER_COMMAND
    list_argv = ["codex", "mcp", "list"]
    remove_argv = ["codex", "mcp", "remove", SERVER_NAME]


class _FileHarness(Harness):
    """Harness we configure by merging one key into its JSON config."""

    # Subclasses define: config path (relative to home), key path, value.
    rel_config: str = ""
    keys: list[str] = []
    value: dict = {}

    @property
    def config_path(self) -> Path:
        return self.home / self.rel_config

    def connect(self) -> HarnessResult:
        try:
            existing = _read_json_key(self.config_path, self.keys)
            if existing == self.value:
                return HarnessResult(self.name, "already")
            _merge_json_key(self.config_path, self.keys, self.value)
        except (ValueError, json.JSONDecodeError) as e:
            return HarnessResult(self.name, "failed", str(e))
        # Read-back from disk — what the harness will actually parse.
        seen = _read_json_key(self.config_path, self.keys)
        if seen != self.value:
            return HarnessResult(
                self.name, "failed", "wrote config but read-back mismatched"
            )
        return HarnessResult(self.name, "registered")

    def disconnect(self) -> HarnessResult:
        try:
            removed = _remove_json_key(self.config_path, self.keys)
        except (ValueError, json.JSONDecodeError) as e:
            return HarnessResult(self.name, "failed", str(e))
        if not removed:
            return HarnessResult(self.name, "skipped", "was not registered")
        if _read_json_key(self.config_path, self.keys) is not None:
            return HarnessResult(self.name, "failed", "key still present")
        return HarnessResult(self.name, "removed")


class OpencodeHarness(_FileHarness):
    name = "opencode"
    rel_config = ".config/opencode/opencode.json"
    keys = ["mcp", SERVER_NAME]
    value = {"type": "local", "command": SERVER_COMMAND, "enabled": True}


class CrushHarness(_FileHarness):
    name = "crush"
    rel_config = ".config/crush/crush.json"
    keys = ["mcp", SERVER_NAME]
    value = {"type": "stdio", "command": SERVER_COMMAND[0],
             "args": SERVER_COMMAND[1:]}


class GeminiHarness(_FileHarness):
    name = "gemini"
    rel_config = ".gemini/settings.json"
    keys = ["mcpServers", SERVER_NAME]
    value = {"command": SERVER_COMMAND[0], "args": SERVER_COMMAND[1:]}


class PiHarness(Harness):
    """pi gets the skill via the shared skill links; its MCP surface is
    unverified (survey), so v0.1 reports that honestly instead of guessing."""

    name = "pi"

    def connect(self) -> HarnessResult:
        return HarnessResult(
            self.name, "skipped",
            "MCP registration not supported yet (skill link only)",
        )

    def disconnect(self) -> HarnessResult:
        return HarnessResult(self.name, "skipped", "nothing registered")


ALL_HARNESSES = [
    ClaudeHarness, CodexHarness, OpencodeHarness,
    CrushHarness, GeminiHarness, PiHarness,
]


def connect_all(home: Path | None = None,
                runner: Runner | None = None) -> list[HarnessResult]:
    """Register with every DETECTED harness; absent ones are skipped.
    A broken harness fails its own row and never stops the others."""
    results = []
    for cls in ALL_HARNESSES:
        h = cls(home=home, runner=runner)
        if not h.detected():
            results.append(HarnessResult(h.name, "skipped", "not installed"))
            continue
        try:
            results.append(h.connect())
        except Exception as e:  # a broken harness must not sink the rest
            results.append(HarnessResult(h.name, "failed", repr(e)))
    return results


def disconnect_all(home: Path | None = None,
                   runner: Runner | None = None) -> list[HarnessResult]:
    results = []
    for cls in ALL_HARNESSES:
        h = cls(home=home, runner=runner)
        if not h.detected():
            results.append(HarnessResult(h.name, "skipped", "not installed"))
            continue
        try:
            results.append(h.disconnect())
        except Exception as e:
            results.append(HarnessResult(h.name, "failed", repr(e)))
    return results
