import sys

import learn
import pytest


@pytest.fixture
def lessons(tmp_path, monkeypatch):
    path = tmp_path / "docs/lessons.md"
    monkeypatch.setattr(learn, "LESSONS", path)
    monkeypatch.setattr(learn, "reindex", lambda: None)
    return path


def run(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["learn.py", *args])
    assert learn.main() == 0
    return capsys.readouterr().out.strip()


def test_add_numbers_lessons_and_skips_duplicates(lessons, monkeypatch, capsys):
    base = ("--cause", "c", "--detect", "d")
    assert run(monkeypatch, capsys, "Do X", *base, "--tags", "a, b") == "recorded L-0001"
    assert run(monkeypatch, capsys, "Do Y", *base) == "recorded L-0002"
    assert run(monkeypatch, capsys, "do x", *base).startswith("no-op")
    text = lessons.read_text(encoding="utf-8")
    assert text.startswith("# Lessons")
    assert "**Tags:** a, b" in text


def test_supersede_and_retire_update_status(lessons, monkeypatch, capsys):
    base = ("--cause", "c", "--detect", "d")
    run(monkeypatch, capsys, "Old rule", *base)
    assert "superseding L-0001" in run(monkeypatch, capsys, "--supersede", "L-0001", "New rule", *base)
    run(monkeypatch, capsys, "--retire", "L-0002", "--reason", "no longer true")
    es = {e["id"]: e["status"] for e in learn.entries(lessons.read_text(encoding="utf-8"))}
    assert es["L-0001"].startswith("superseded by L-0002")
    assert es["L-0002"].startswith("retired ")
    assert "**Supersedes:** L-0001" in lessons.read_text(encoding="utf-8")


def test_unknown_id_is_an_error(lessons, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["learn.py", "--retire", "L-0099", "--reason", "x"])
    with pytest.raises(SystemExit):
        learn.main()


def test_written_file_passes_the_lessons_invariant(lessons, monkeypatch, capsys):
    import invariants

    run(monkeypatch, capsys, "Rule", "--cause", "c", "--detect", "d")
    monkeypatch.setattr(invariants, "ROOT", lessons.parent.parent)
    assert invariants.check_lessons() == []
