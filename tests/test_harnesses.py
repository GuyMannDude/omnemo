"""Per-adapter tests for harness MCP registration (SPEC: each harness config
format is its own small adapter with its own test, and every write must be
read back)."""

import json
import tomllib

import pytest

from omnemo.omarchy import harnesses as h
from omnemo.omarchy.harnesses import (
    ClaudeHarness,
    CodexHarness,
    CrushHarness,
    GeminiHarness,
    OpencodeHarness,
    PiHarness,
    connect_all,
)


# ---------- file adapters ----------

FILE_ADAPTERS = [
    (OpencodeHarness, ["mcp", "omnemo"]),
    (CrushHarness, ["mcp", "omnemo"]),
    (GeminiHarness, ["mcpServers", "omnemo"]),
]


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_registers_and_reads_back(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    result = adapter.connect()
    assert result.action == "registered"
    data = json.loads(adapter.config_path.read_text())
    node = data
    for key in keys:
        node = node[key]
    assert node == cls.value


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_preserves_existing_config(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text(
        json.dumps({"theme": "dark", keys[0]: {"other": {"command": "x"}}})
    )
    assert adapter.connect().action == "registered"
    data = json.loads(adapter.config_path.read_text())
    assert data["theme"] == "dark"
    assert data[keys[0]]["other"] == {"command": "x"}


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_idempotent(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    assert adapter.connect().action == "registered"
    assert adapter.connect().action == "already"


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_disconnect_removes_only_ours(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text(
        json.dumps({keys[0]: {"other": {"command": "x"}}})
    )
    adapter.connect()
    result = adapter.disconnect()
    assert result.action == "removed"
    data = json.loads(adapter.config_path.read_text())
    assert "omnemo" not in data[keys[0]]
    assert data[keys[0]]["other"] == {"command": "x"}


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_disconnect_when_absent(tmp_path, cls, keys):
    assert cls(home=tmp_path).disconnect().action == "skipped"


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_corrupt_config_fails_cleanly(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text("{not json")
    result = adapter.connect()
    assert result.action == "failed"
    # The corrupt file must not be clobbered by a failed connect.
    assert adapter.config_path.read_text() == "{not json"


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_preserves_file_mode(tmp_path, cls, keys):
    # These configs hold API keys; a rewrite must not widen a user's 0600.
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text("{}")
    adapter.config_path.chmod(0o600)
    assert adapter.connect().action == "registered"
    assert adapter.config_path.stat().st_mode & 0o777 == 0o600
    assert adapter.disconnect().action == "removed"
    assert adapter.config_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_disconnect_corrupt_config_fails_cleanly(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text("{not json")
    assert adapter.disconnect().action == "failed"
    assert adapter.config_path.read_text() == "{not json"


@pytest.mark.parametrize("cls,keys", FILE_ADAPTERS)
def test_file_adapter_non_object_section_fails(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text(json.dumps({keys[0]: "a string"}))
    assert adapter.connect().action == "failed"


# ---------- CLI adapters ----------

GET_OK = "Command: omnemo\n  Args: serve"
GET_STALE = "Command: /old/dead/venv/bin/omnemo\n  Args: serve"

# What `codex mcp add` leaves in ~/.codex/config.toml (the fake runner
# does not write it, so Codex tests seed it).
CODEX_TABLE = '[mcp_servers.omnemo]\ncommand = "omnemo"\nargs = ["serve"]\n'
# ...and the same table once `omnemo setup` has added the startup keys.
CODEX_TABLE_TUNED = CODEX_TABLE + (
    'required = true\nstartup_timeout_sec = 30\n'
    'default_tools_approval_mode = "approve"\n'
)


def _seed_codex(home, text=CODEX_TABLE):
    path = home / ".codex/config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _codex_table(home):
    data = tomllib.loads((home / ".codex/config.toml").read_text())
    return data["mcp_servers"]["omnemo"]


class FakeRunner:
    """Scripted CLI: maps the subcommand ('list'/'get'/'add'/'remove') to a
    queue of (exit_code, output) responses; the last response repeats."""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        verb = argv[2]  # e.g. ["claude", "mcp", "list"]
        queue = self.script[verb]
        return queue.pop(0) if len(queue) > 1 else queue[0]


def _verbs(runner):
    return [a[2] for a in runner.calls]


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_registers_with_readback(tmp_path, cls):
    if cls is CodexHarness:
        _seed_codex(tmp_path)
    runner = FakeRunner({
        "list": [(0, "nothing here"), (0, "omnemo: omnemo serve")],
        "get": [(0, GET_OK)],
        "add": [(0, "Added")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "registered"
    assert "add" in _verbs(runner)


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_add_without_readback_is_failure(tmp_path, cls):
    runner = FakeRunner({
        "list": [(0, "nothing here")],  # never shows omnemo
        "get": [(1, "not found")],
        "add": [(0, "Added")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "failed"
    assert "read-back" in result.detail


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_already_registered(tmp_path, cls):
    if cls is CodexHarness:
        _seed_codex(tmp_path, CODEX_TABLE_TUNED)
    runner = FakeRunner({
        "list": [(0, "omnemo: omnemo serve")],
        "get": [(0, GET_OK)],
        "add": [],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "already"
    assert "add" not in _verbs(runner)


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_repairs_stale_registration(tmp_path, cls):
    if cls is CodexHarness:
        _seed_codex(tmp_path)
    # Registered under our name but launching a dead binary: must be
    # replaced, never reported "already" (reviewer finding, 2026-08-28).
    runner = FakeRunner({
        "list": [(0, "omnemo: /old/dead/venv/bin/omnemo serve")],
        "get": [(0, GET_STALE), (0, GET_OK)],
        "remove": [(0, "Removed")],
        "add": [(0, "Added")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "registered"
    assert "stale" in result.detail
    assert _verbs(runner).count("remove") == 1
    assert _verbs(runner).count("add") == 1


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_broken_cli_fails_cleanly(tmp_path, cls):
    runner = FakeRunner({
        "list": [(1, "mise ERROR install failed")],
        "get": [(1, "mise ERROR install failed")],
        "add": [(1, "mise ERROR install failed")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "failed"


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_disconnect_broken_cli_is_failure(tmp_path, cls):
    # A broken read surface must never report "was not registered":
    # skipped would be an assertion the code has no evidence for.
    runner = FakeRunner({
        "list": [(1, "mise ERROR install failed")],
        "get": [(1, "mise ERROR install failed")],
        "remove": [(0, "Removed")],
    })
    result = cls(home=tmp_path, runner=runner).disconnect()
    assert result.action == "failed"
    assert "remove" not in _verbs(runner)


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_remove_verifies(tmp_path, cls):
    runner = FakeRunner({
        "list": [(0, "omnemo: omnemo serve"), (0, "")],
        "get": [(0, GET_OK)],
        "remove": [(0, "Removed")],
    })
    assert cls(home=tmp_path, runner=runner).disconnect().action == "removed"


# ---------- pi + orchestration ----------

def test_pi_is_honest_about_no_mcp(tmp_path):
    result = PiHarness(home=tmp_path).connect()
    assert result.action == "skipped"
    assert "not supported" in result.detail


def test_disconnect_all_skips_undetected_and_survives_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(
        h.shutil, "which", lambda name: "/x/crush" if name == "crush" else None
    )
    crush_cfg = tmp_path / ".config/crush/crush.json"
    crush_cfg.parent.mkdir(parents=True)
    crush_cfg.write_text("{broken")
    from omnemo.omarchy.harnesses import disconnect_all

    results = {r.harness: r for r in disconnect_all(home=tmp_path)}
    assert results["crush"].action == "failed"
    assert results["claude"].action == "skipped"
    assert len(results) == 6


def test_cli_exit_code_reflects_failed_rows(tmp_path, monkeypatch):
    # Install scripts branch on `omnemo connect`'s exit code: any FAIL row
    # must exit 1, all-ok must exit 0.
    from omnemo import cli
    from omnemo.omarchy import harnesses as hmod

    monkeypatch.setattr(
        hmod.shutil, "which", lambda name: "/x/crush" if name == "crush" else None
    )
    monkeypatch.setattr(hmod.Path, "home", classmethod(lambda cls: tmp_path))
    assert cli.main(["connect"]) == 0  # crush registers, rest skipped
    (tmp_path / ".config/crush/crush.json").write_text("{broken")
    assert cli.main(["connect"]) == 1


def test_connect_all_skips_undetected_and_survives_failures(tmp_path, monkeypatch):
    # Only "crush" is installed; its config dir is a broken file.
    monkeypatch.setattr(
        h.shutil, "which", lambda name: "/x/crush" if name == "crush" else None
    )
    crush_cfg = tmp_path / ".config/crush/crush.json"
    crush_cfg.parent.mkdir(parents=True)
    crush_cfg.write_text("{broken")
    results = {r.harness: r for r in connect_all(home=tmp_path)}
    assert results["crush"].action == "failed"
    assert results["claude"].action == "skipped"
    assert results["gemini"].action == "skipped"
    # One harness failing never aborts the sweep.
    assert len(results) == 6


# ---------- Codex startup keys (gate-2 F12, 2026-10-27) ----------

def _codex_registered_runner():
    return FakeRunner({
        "list": [(0, "nothing here"), (0, "omnemo: omnemo serve")],
        "get": [(0, GET_OK)],
        "add": [(0, "Added")],
    })


def test_codex_writes_startup_keys_after_add(tmp_path):
    _seed_codex(tmp_path)
    result = CodexHarness(home=tmp_path, runner=_codex_registered_runner()).connect()
    assert result.action == "registered"
    assert "startup keys" in result.detail
    table = _codex_table(tmp_path)
    assert table["required"] is True
    assert table["startup_timeout_sec"] == 30
    assert table["default_tools_approval_mode"] == "approve"
    # What `codex mcp add` wrote is untouched.
    assert table["command"] == "omnemo" and table["args"] == ["serve"]


def test_codex_startup_keys_idempotent(tmp_path):
    _seed_codex(tmp_path)
    runner = FakeRunner({
        "list": [(0, "omnemo: omnemo serve")],
        "get": [(0, GET_OK)],
        "add": [],
    })
    assert CodexHarness(home=tmp_path, runner=runner).connect().action == "registered"
    assert CodexHarness(home=tmp_path, runner=runner).connect().action == "already"


def test_codex_startup_keys_replace_ours_and_keep_the_rest(tmp_path):
    _seed_codex(tmp_path, (
        'model = "gpt-5"\n\n'
        '[mcp_servers.omnemo]\n'
        'command = "omnemo"\n'
        'args = ["serve"]\n'
        'required = false\n'
        'env = { OMNEMO_LOG = "debug" }\n\n'
        '[mcp_servers.other]\n'
        'command = "x"\n'
    ))
    result = CodexHarness(home=tmp_path, runner=_codex_registered_runner()).connect()
    assert result.action == "registered"
    text = (tmp_path / ".codex/config.toml").read_text()
    data = tomllib.loads(text)
    assert data["model"] == "gpt-5"
    assert data["mcp_servers"]["other"] == {"command": "x"}
    table = data["mcp_servers"]["omnemo"]
    assert table["required"] is True
    assert table["env"] == {"OMNEMO_LOG": "debug"}
    assert text.count("required =") == 1


def test_codex_missing_table_after_add_is_failure(tmp_path):
    # Registered per the CLI, but no table to tune: say so, never assume.
    result = CodexHarness(home=tmp_path, runner=_codex_registered_runner()).connect()
    assert result.action == "failed"
    assert "no [mcp_servers.omnemo]" in result.detail


def test_codex_corrupt_toml_fails_cleanly(tmp_path):
    path = _seed_codex(tmp_path, "[mcp_servers.omnemo\ncommand = ")
    result = CodexHarness(home=tmp_path, runner=_codex_registered_runner()).connect()
    assert result.action == "failed"
    assert path.read_text() == "[mcp_servers.omnemo\ncommand = "


def test_codex_startup_keys_preserve_file_mode(tmp_path):
    path = _seed_codex(tmp_path)
    path.chmod(0o600)
    assert CodexHarness(home=tmp_path, runner=_codex_registered_runner()).connect().action == "registered"
    assert path.stat().st_mode & 0o777 == 0o600


def test_codex_registered_before_the_keys_existed_gets_them(tmp_path):
    # An install from before 0.2.1.dev3: the CLI says registered, the
    # table lacks the keys. `omnemo setup` must add them, and say so.
    _seed_codex(tmp_path)
    runner = FakeRunner({
        "list": [(0, "omnemo: omnemo serve")],
        "get": [(0, GET_OK)],
        "add": [],
    })
    result = CodexHarness(home=tmp_path, runner=runner).connect()
    assert result.action == "registered"
    assert result.detail == "startup keys written"
    assert "add" not in _verbs(runner)
    assert _codex_table(tmp_path)["required"] is True
