import os
from pathlib import Path


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
