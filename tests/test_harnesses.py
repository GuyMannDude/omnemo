"""Per-adapter tests for harness MCP registration (SPEC: each harness config
format is its own small adapter with its own test, and every write must be
read back)."""

import json

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
def test_file_adapter_non_object_section_fails(tmp_path, cls, keys):
    adapter = cls(home=tmp_path)
    adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.config_path.write_text(json.dumps({keys[0]: "a string"}))
    assert adapter.connect().action == "failed"


# ---------- CLI adapters ----------

class FakeRunner:
    """Scripted CLI: maps the subcommand ('list'/'add'/'remove') to a queue
    of (exit_code, output) responses."""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        verb = argv[2]  # e.g. ["claude", "mcp", "list"]
        queue = self.script[verb]
        return queue.pop(0) if len(queue) > 1 else queue[0]


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_registers_with_readback(tmp_path, cls):
    runner = FakeRunner({
        "list": [(0, "nothing here"), (0, "omnemo: omnemo serve")],
        "add": [(0, "Added")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "registered"
    assert any(a[2] == "add" for a in runner.calls)


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_add_without_readback_is_failure(tmp_path, cls):
    runner = FakeRunner({
        "list": [(0, "nothing here")],  # never shows omnemo
        "add": [(0, "Added")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "failed"
    assert "read-back" in result.detail


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_already_registered(tmp_path, cls):
    runner = FakeRunner({"list": [(0, "omnemo: omnemo serve")], "add": []})
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "already"
    assert not any(a[2] == "add" for a in runner.calls)


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_broken_cli_fails_cleanly(tmp_path, cls):
    runner = FakeRunner({
        "list": [(1, "mise ERROR install failed")],
        "add": [(1, "mise ERROR install failed")],
    })
    result = cls(home=tmp_path, runner=runner).connect()
    assert result.action == "failed"


@pytest.mark.parametrize("cls", [ClaudeHarness, CodexHarness])
def test_cli_adapter_remove_verifies(tmp_path, cls):
    runner = FakeRunner({
        "list": [(0, "omnemo: omnemo serve"), (0, "")],
        "remove": [(0, "Removed")],
    })
    assert cls(home=tmp_path, runner=runner).disconnect().action == "removed"


# ---------- pi + orchestration ----------

def test_pi_is_honest_about_no_mcp(tmp_path):
    result = PiHarness(home=tmp_path).connect()
    assert result.action == "skipped"
    assert "not supported" in result.detail


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
