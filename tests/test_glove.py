"""Glove setup: skill links, plugin copy, unit write — all against a temp
home, never the real one."""


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
    assert any("FAILED" in line and "skill" in line for line in lines)
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
