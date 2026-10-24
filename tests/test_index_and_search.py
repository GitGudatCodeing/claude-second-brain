import os
from pathlib import Path

import pytest


def counts(server):
    con = server.db()
    return tuple(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("chunks", "chunks_fts", "chunks_vec_rowids"))


def test_index_then_resync_is_incremental(index, vault):
    first = index.index_paths([str(vault)])
    assert "'added': 3" in first
    assert "'unchanged': 3" in index.index_paths()
    n = counts(index)
    assert n[0] == n[1] == n[2] > 0


def test_changed_and_deleted_files_are_picked_up(index, vault):
    index.index_paths([str(vault)])
    garden = vault / "notes/garden.md"
    garden.write_text("# Garden\n\nNow the chillies need water too.\n", encoding="utf-8")
    os.utime(garden, (garden.stat().st_atime, garden.stat().st_mtime + 5))
    (vault / "notes/bikes.md").unlink()
    out = index.index_paths()
    assert "'updated': 1" in out and "'removed': 1" in out
    paths = {Path(p).name for p, *_ in index.hybrid_search("chillies water", 5)}
    assert "garden.md" in paths and "bikes.md" not in paths
    n = counts(index)
    assert n[0] == n[1] == n[2]


def test_touched_but_unchanged_file_is_not_reembedded(index, vault):
    index.index_paths([str(vault)])
    garden = vault / "notes/garden.md"
    os.utime(garden, (garden.stat().st_atime, garden.stat().st_mtime + 5))
    assert "'unchanged': 3" in index.index_paths()


def test_hybrid_search_ranks_the_matching_note_first(index, vault):
    index.index_paths([str(vault)])
    for mode in ("hybrid", "fts", "vec"):
        top = index.hybrid_search("how often do the tomatoes need water", 3, mode=mode)
        assert Path(top[0][0]).name == "garden.md", mode
        assert top[0][1] == "Garden > Watering"


def test_ignored_files_are_never_searchable(index, vault):
    index.index_paths([str(vault)])
    paths = [p for p, *_ in index.hybrid_search("secret plans tomatoes diary", 10)]
    assert not any("private" in p or "node_modules" in p for p in paths)


def test_path_prefix_filters_results(index, vault):
    index.index_paths([str(vault)])
    hits = index.hybrid_search("tomatoes", 5, path_prefix=str((vault / "code").resolve()))
    assert hits and all(Path(p).name == "app.py" for p, *_ in hits)


def test_fts_query_drops_stopwords_but_never_empties():
    import server

    assert server.fts_query("what is the garden") == '"garden"'
    assert server.fts_query("what is it") == '"what" OR "is" OR "it"'
    assert server.fts_query("???") is None


def test_get_note_only_reads_indexed_files(index, vault):
    index.index_paths([str(vault)])
    assert "tomatoes" in index.get_note(str(vault / "notes/garden.md"))
    assert index.get_note(str(vault / "notes/private/diary.md")).startswith("Not in index")


def test_remove_source_drops_everything(index, vault):
    index.index_paths([str(vault)])
    assert "3 files" in index.remove_source(str(vault))
    assert counts(index) == (0, 0, 0)
    assert index.list_sources() == "No sources registered."


def test_path_prefix_accepts_relative_and_either_slash(index, vault):
    index.index_paths([str(vault)])
    for prefix in ("code", "./code/", str(vault / "code").replace("\\", "/"), str(vault / "code").upper()):
        hits = index.hybrid_search("tomatoes", 5, path_prefix=prefix)
        assert hits and all(Path(p).name == "app.py" for p, *_ in hits), prefix


def test_path_prefix_searches_beyond_the_unfiltered_pool(index, vault):
    for i in range(30):  # 30 notes that outrank the code file for this query
        (vault / f"notes/t{i}.md").write_text(f"# T{i}\n\ntomatoes water tomatoes {i}\n", encoding="utf-8")
    index.index_paths([str(vault)])
    assert all(Path(p).parent.name != "code" for p, *_ in index.hybrid_search("tomatoes water", 2))
    hits = index.hybrid_search("tomatoes water", 2, path_prefix="code")
    assert [Path(p).name for p, *_ in hits] == ["app.py"]


def test_failed_embedding_leaves_the_old_version_searchable(index, vault, monkeypatch):
    index.index_paths([str(vault)])
    garden = vault / "notes/garden.md"
    garden.write_text("# Garden\n\nNew text about basil.\n", encoding="utf-8")
    os.utime(garden, (garden.stat().st_atime, garden.stat().st_mtime + 5))
    real = index.embed

    def broken(texts):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(index, "embed", broken)
    with pytest.raises(RuntimeError):
        index.index_paths()
    index.db().commit()  # a later unrelated commit must not keep a half-indexed file
    monkeypatch.setattr(index, "embed", real)
    assert "'updated': 1" in index.index_paths()
    assert Path(index.hybrid_search("basil", 1)[0][0]).name == "garden.md"


def test_file_that_becomes_too_big_is_dropped(index, vault, monkeypatch):
    index.index_paths([str(vault)])
    monkeypatch.setattr(index, "MAX_FILE_BYTES", 10)
    garden = vault / "notes/garden.md"
    os.utime(garden, (garden.stat().st_atime, garden.stat().st_mtime + 5))
    index.index_paths()
    assert all(Path(p).name != "garden.md" for p, *_ in index.hybrid_search("tomatoes water July", 5))


def test_remove_source_does_not_treat_underscore_as_wildcard(index, tmp_path):
    a, b = tmp_path / "notes_a", tmp_path / "notes-a"
    for d in (a, b):
        d.mkdir()
        (d / "n.md").write_text("# N\n\nhello\n", encoding="utf-8")
    index.index_paths([str(a), str(b)])
    assert "(1 files" in index.remove_source(str(a))
    assert "1 files" in index.list_sources()


def test_reindex_hook_works_for_a_vault_under_a_skip_dir_name(index, tmp_path, monkeypatch):
    import io
    import json

    import reindex_hook

    vault = tmp_path / "build" / "vault"
    vault.mkdir(parents=True)
    note = vault / "n.md"
    note.write_text("# N\n\nfirst\n", encoding="utf-8")
    index.index_paths([str(vault)])
    note.write_text("# N\n\nsecond version about basil\n", encoding="utf-8")
    os.utime(note, (note.stat().st_atime, note.stat().st_mtime + 5))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(note)}})))
    reindex_hook.main()
    assert "basil" in index.hybrid_search("basil", 1)[0][2]


def test_file_vanishing_mid_sync_keeps_the_rest(index, vault, monkeypatch):
    real_stat = Path.stat

    def flaky_stat(self, *a, **k):
        if self.name == "bikes.md":
            raise FileNotFoundError(self)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    out = index.index_paths([str(vault)])
    assert "'added': 2" in out
    assert Path(index.hybrid_search("tomatoes water", 1)[0][0]).name in ("garden.md", "app.py")


def test_bad_path_registers_nothing(index, vault):
    out = index.index_paths([str(vault), str(vault / "typo")])
    assert out.startswith("Path does not exist") and "typo" in out
    index.db().commit()
    assert index.list_sources() == "No sources registered."


def test_missing_source_keeps_its_index(index, tmp_path):
    src = tmp_path / "drive"
    src.mkdir()
    (src / "n.md").write_text("# N\n\nbasil on the balcony\n", encoding="utf-8")
    index.index_paths([str(src)])
    src.rename(tmp_path / "unplugged")
    assert "missing on disk" in index.index_paths()
    assert "1 files" in index.list_sources()


def test_model_change_is_reported_and_reindex_rebuilds(index, vault, monkeypatch):
    index.index_paths([str(vault)])
    monkeypatch.setattr(index, "MODEL_NAME", "other/model")
    assert "Run index_paths with reindex=True" in index.search_notes("tomatoes")
    assert "reindex=True" in index.index_paths()
    assert "'added': 3" in index.index_paths(reindex=True)
    assert "garden.md" in index.search_notes("tomatoes water")


def test_get_note_on_a_deleted_file_explains(index, vault):
    index.index_paths([str(vault)])
    (vault / "notes/garden.md").unlink()
    assert "no longer on disk" in index.get_note(str(vault / "notes/garden.md"))


def test_cli_help_version_index_and_search(index, vault, capsys):
    with pytest.raises(SystemExit):
        index.main(["--help"])
    assert "serves MCP over stdio" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        index.main(["--version"])
    assert capsys.readouterr().out.startswith("vault-index ")
    index.main(["index", str(vault)])
    assert "'added': 3" in capsys.readouterr().out
    index.main(["search", "tomatoes water", "-n", "1"])
    assert "garden.md" in capsys.readouterr().out
