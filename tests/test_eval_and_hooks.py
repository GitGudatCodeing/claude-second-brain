import json

import handoff_common
import invariants
import run_eval


def result(rel_path, heading):
    return (str(run_eval.ROOT / rel_path), heading, "text", 0.1)


def test_perfect_ranking_scores_one():
    q = {"relevant": [{"path": "a.md", "heading": "", "grade": 2}, {"path": "b.md", "heading": "X", "grade": 1}]}
    s, _ = run_eval.score(q, [result("a.md", "A"), result("b.md", "B > X")])
    assert s == {"ndcg@5": 1.0, "mrr": 1.0, "recall@5": 1.0}


def test_a_label_counts_once_and_misses_score_zero():
    q = {"relevant": [{"path": "a.md", "heading": "", "grade": 2}]}
    s, found = run_eval.score(q, [result("z.md", ""), result("a.md", "1"), result("a.md", "2")])
    assert s["mrr"] == 0.5 and s["recall@5"] == 1.0 and len(found) == 1
    s, _ = run_eval.score(q, [result("z.md", "")])
    assert s == {"ndcg@5": 0.0, "mrr": 0.0, "recall@5": 0.0}


def test_context_tokens_reads_latest_usage_and_survives_partial_lines(tmp_path):
    t = tmp_path / "t.jsonl"
    lines = [
        '{"broken": ',
        json.dumps({"message": {"usage": {"input_tokens": 1}}}),
        json.dumps({"isSidechain": True, "message": {"usage": {"input_tokens": 999}}}),
        json.dumps({"message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": 200,
                                          "cache_creation_input_tokens": 5}}}),
        json.dumps({"type": "user", "message": {"content": "hi"}}),
    ]
    t.write_text("\n".join(lines), encoding="utf-8")
    assert handoff_common.context_tokens(handoff_common.read_entries(t)) == 215


def test_abs_paths_expands_project_dir():
    root = invariants.ROOT.as_posix()
    cmd = 'uv run --project "$CLAUDE_PROJECT_DIR"/mcp python $CLAUDE_PROJECT_DIR/mcp/x.py --flag'
    assert invariants.abs_paths(cmd) == [f"{root}/mcp", f"{root}/mcp/x.py"]


def test_hook_check_flags_a_missing_script(tmp_path, monkeypatch):
    (tmp_path / ".claude").mkdir()
    (tmp_path / "mcp/.venv").mkdir(parents=True)
    hook = {"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR"/mcp/reindex_hook.py'}
    settings = {"hooks": {"PostToolUse": [{"hooks": [hook]}]}}
    (tmp_path / ".claude/settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(invariants, "ROOT", tmp_path)
    assert any("hook path missing" in p for p in invariants.check_hook())
    (tmp_path / "mcp/reindex_hook.py").write_text("", encoding="utf-8")
    assert invariants.check_hook() == []
