"""Glove setup: skill links, plugin copy, unit write, bar layout — all
against a temp home, never the real one."""

import json

import pytest

from omnemo.omarchy import glove


def test_install_skill_copies_and_links(tmp_path):
    lines = glove.install_skill(tmp_path)
    skill_home = tmp_path / ".local/share/omnemo/skill"
    assert (skill_home / "SKILL.md").exists()
    for rel in glove.SKILL_LINK_DIRS:
        link = tmp_path / rel / "omnemo"
        assert link.is_symlink() and link.resolve() == skill_home.resolve()
    assert any("installed" in line for line in lines)


def test_install_skill_leaves_foreign_dir_alone(tmp_path):
    foreign = tmp_path / ".claude/skills/omnemo"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("someone else's omnemo skill")
    lines = glove.install_skill(tmp_path)
    assert (foreign / "SKILL.md").read_text() == "someone else's omnemo skill"
    assert any("LEFT ALONE" in line for line in lines)


def test_install_skill_idempotent(tmp_path):
    glove.install_skill(tmp_path)
    lines = glove.install_skill(tmp_path)
    assert any("already linked" in line for line in lines)


def test_install_plugin(tmp_path):
    glove.install_plugin(tmp_path)
    plugin = tmp_path / ".config/omarchy/plugins/omnemo.memory"
    assert (plugin / "manifest.json").exists()
    assert (plugin / "BarWidget.qml").exists()


def test_install_warm_unit_writes_unit(tmp_path):
    lines = glove.install_warm_unit(tmp_path, enable=False)
    unit = tmp_path / ".config/systemd/user/omnemo-warm.service"
    assert unit.exists()
    assert "omnemo warm" in unit.read_text()
    assert any("unit written" in line for line in lines)


def test_setup_one_failing_step_does_not_stop_the_others(tmp_path, monkeypatch):
    from omnemo.omarchy import harnesses as h

    monkeypatch.setattr(h.shutil, "which", lambda name: None)

    def boom(home):
        raise RuntimeError("skill step exploded")

    monkeypatch.setattr(glove, "install_skill", boom)
    monkeypatch.setattr(
        glove, "install_warm_unit", lambda home: ["warm-up: stubbed"]
    )
    lines, results = glove.setup(home=tmp_path)
    assert any(line.startswith("[fail] skill:") for line in lines)
    # The plugin step after the explosion still ran.
    assert (tmp_path / ".config/omarchy/plugins/omnemo.memory/manifest.json").exists()
    # And the harness sweep still reported all six rows.
    assert len(results) == 6


def test_teardown_removes_only_ours(tmp_path, monkeypatch):
    from omnemo.omarchy import harnesses as h

    # No harness "installed": teardown must never shell out to real CLIs.
    monkeypatch.setattr(h.shutil, "which", lambda name: None)
    glove.install_skill(tmp_path)
    glove.install_plugin(tmp_path)
    glove.install_warm_unit(tmp_path, enable=False)
    # A foreign skill link that must survive teardown.
    other = tmp_path / ".claude/skills/other"
    other.symlink_to(tmp_path / ".local/share/omnemo/elsewhere")
    _lines, _results = glove.teardown(home=tmp_path)
    assert not (tmp_path / ".claude/skills/omnemo").exists()
    assert not (tmp_path / ".config/omarchy/plugins/omnemo.memory").exists()
    assert other.is_symlink()
    # The skill copy and store stay — they are the user's.
    assert (tmp_path / ".local/share/omnemo/skill/SKILL.md").exists()


# ---------- bar widget opt-in (#1) ----------

SHELL = {
    "version": 1,
    "bar": {
        "position": "top",
        "layout": {"left": ["omarchy.menu"], "right": ["omarchy.tray", "omarchy.power"]},
    },
    "disabledPlugins": ["omarchy.dock"],
}


def _shell_json(home, data=SHELL):
    path = home / ".config/omarchy/shell.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)
    return path


def _quiet_setup(monkeypatch):
    # No harness CLIs on the box, no real systemctl.
    from omnemo.omarchy import harnesses as h

    monkeypatch.setattr(h.shutil, "which", lambda name: None)
    monkeypatch.setattr(glove, "install_warm_unit", lambda home: ["warm-up: stubbed"])


def test_setup_leaves_shell_json_alone(tmp_path, monkeypatch):
    _quiet_setup(monkeypatch)
    path = _shell_json(tmp_path)
    before = path.read_bytes()
    lines, _results = glove.setup(home=tmp_path)
    assert path.read_bytes() == before
    assert not any(line.startswith("bar:") for line in lines)
    # The plugin files are still installed (Omarchy lists them as disabled).
    assert (tmp_path / ".config/omarchy/plugins/omnemo.memory/manifest.json").exists()


def test_setup_without_shell_json_does_not_create_one(tmp_path, monkeypatch):
    _quiet_setup(monkeypatch)
    glove.setup(home=tmp_path)
    assert not (tmp_path / ".config/omarchy/shell.json").exists()


def test_setup_bar_adds_the_widget(tmp_path, monkeypatch):
    _quiet_setup(monkeypatch)
    path = _shell_json(tmp_path)
    lines, _results = glove.setup(home=tmp_path, bar=True)
    assert any(line.startswith("bar: omnemo.memory added") for line in lines)
    assert json.loads(path.read_text())["bar"]["layout"]["right"][-1] == "omnemo.memory"


def test_bar_on_adds_once_and_keeps_the_rest(tmp_path):
    path = _shell_json(tmp_path)
    first = glove.bar_on(tmp_path)
    second = glove.bar_on(tmp_path)
    data = json.loads(path.read_text())
    assert data["bar"]["layout"]["right"] == ["omarchy.tray", "omarchy.power", "omnemo.memory"]
    assert data["bar"]["layout"]["left"] == ["omarchy.menu"]
    assert data["bar"]["position"] == "top"
    assert data["version"] == 1
    assert data["disabledPlugins"] == ["omarchy.dock"]
    assert any("added" in line for line in first)
    assert any("already on the bar (right)" in line for line in second)
    # Omarchy's own writer leaves shell.json at 0600; ours must not widen it.
    assert path.stat().st_mode & 0o777 == 0o600


def test_bar_on_mirrors_object_entries(tmp_path):
    # Stock shell.json on Omarchy master lists widgets as {"id": ...}.
    data = {"bar": {"layout": {"left": [{"id": "omarchy.menu"}], "right": [{"id": "omarchy.tray"}]}}}
    path = _shell_json(tmp_path, data)
    glove.bar_on(tmp_path)
    glove.bar_on(tmp_path)
    right = json.loads(path.read_text())["bar"]["layout"]["right"]
    assert right == [{"id": "omarchy.tray"}, {"id": "omnemo.memory"}]


def test_bar_on_leaves_a_moved_widget_where_it_is(tmp_path):
    data = {"bar": {"layout": {"left": ["omnemo.memory"], "right": ["omarchy.tray"]}}}
    path = _shell_json(tmp_path, data)
    before = path.read_bytes()
    lines = glove.bar_on(tmp_path)
    assert path.read_bytes() == before
    assert any("already on the bar (left)" in line for line in lines)


def test_bar_on_clears_an_earlier_plugin_disable(tmp_path):
    data = {"bar": {"layout": {"right": []}}, "disabledPlugins": ["omarchy.dock", "omnemo.memory"]}
    path = _shell_json(tmp_path, data)
    lines = glove.bar_on(tmp_path)
    assert json.loads(path.read_text())["disabledPlugins"] == ["omarchy.dock"]
    assert any("re-enabled" in line for line in lines)


def test_bar_on_without_a_layout_fails_cleanly(tmp_path):
    # Never invent a layout: a file holding only our widget would blank the bar.
    with pytest.raises(RuntimeError, match="omarchy bar move omnemo.memory"):
        glove.bar_on(tmp_path)
    assert not (tmp_path / ".config/omarchy/shell.json").exists()
    path = _shell_json(tmp_path, {"version": 1})
    with pytest.raises(RuntimeError):
        glove.bar_on(tmp_path)
    assert json.loads(path.read_text()) == {"version": 1}


def test_bar_off_removes_and_is_a_noop_when_absent(tmp_path):
    path = _shell_json(tmp_path)
    glove.bar_on(tmp_path)
    lines = glove.bar_off(tmp_path)
    data = json.loads(path.read_text())
    assert data["bar"]["layout"] == SHELL["bar"]["layout"]
    assert data["disabledPlugins"] == ["omarchy.dock"]
    assert any("removed" in line for line in lines)
    before = path.read_bytes()
    lines = glove.bar_off(tmp_path)
    assert path.read_bytes() == before
    assert any("not on the bar" in line for line in lines)


def test_bar_off_without_shell_json_creates_nothing(tmp_path):
    lines = glove.bar_off(tmp_path)
    assert any("not on the bar" in line for line in lines)
    assert not (tmp_path / ".config/omarchy/shell.json").exists()


def test_cli_bar_and_setup_bar(tmp_path, monkeypatch):
    from omnemo import cli

    _quiet_setup(monkeypatch)
    monkeypatch.setattr(glove.Path, "home", classmethod(lambda cls: tmp_path))
    # No layout yet: a clear failure, exit 1, nothing written.
    assert cli.main(["bar", "on"]) == 1
    assert not (tmp_path / ".config/omarchy/shell.json").exists()
    path = _shell_json(tmp_path)
    assert cli.main(["bar", "on"]) == 0
    assert "omnemo.memory" in json.loads(path.read_text())["bar"]["layout"]["right"]
    assert (tmp_path / ".config/omarchy/plugins/omnemo.memory/manifest.json").exists()
    assert cli.main(["bar", "off"]) == 0
    assert "omnemo.memory" not in json.loads(path.read_text())["bar"]["layout"]["right"]
    assert cli.main(["setup"]) == 0
    assert "omnemo.memory" not in json.loads(path.read_text())["bar"]["layout"]["right"]
    assert cli.main(["setup", "--bar"]) == 0
    assert "omnemo.memory" in json.loads(path.read_text())["bar"]["layout"]["right"]
