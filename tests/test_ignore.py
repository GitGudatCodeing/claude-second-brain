from pathlib import Path

import invariants
import server


def test_load_ignores_strips_comments_slashes_and_case(tmp_path):
    (tmp_path / ".indexignore").write_text("# comment\nMCP/\n\\Docs\\auto  # why\n\n", encoding="utf-8")
    assert server.load_ignores(tmp_path) == ["mcp", "docs/auto"]


def test_is_ignored_matches_folder_and_file_not_prefix(tmp_path):
    igs = ["mcp", "docs/auto"]
    assert server.is_ignored(tmp_path / "mcp", tmp_path, igs)
    assert server.is_ignored(tmp_path / "mcp/server.py", tmp_path, igs)
    assert server.is_ignored(tmp_path / "Docs/Auto/x.md", tmp_path, igs)
    assert not server.is_ignored(tmp_path / "mcpx/server.py", tmp_path, igs)
    assert not server.is_ignored(Path("/elsewhere/mcp"), tmp_path, igs)


def test_iter_files_skips_ignored_dirs_and_types(vault):
    found = {p.relative_to(vault).as_posix() for p in server.iter_files(vault)}
    assert found == {"notes/garden.md", "notes/bikes.md", "code/app.py"}


def test_invariants_walk_mirrors_server(vault):
    """invariants.py re-implements the walk without importing server; they must agree."""
    ours = {p for p in invariants.walk(vault) if p.suffix in invariants.INDEXED_EXT}
    theirs = set(server.iter_files(vault))
    assert ours == theirs
    assert invariants.ignores_for(vault) == server.load_ignores(vault)


def test_extension_and_skip_lists_match():
    assert invariants.INDEXED_EXT == server.EXTENSIONS
    assert invariants.SKIP_DIRS == server.SKIP_DIRS
