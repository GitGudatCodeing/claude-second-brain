import json
import os

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


def test_grep_baseline_ranks_by_matching_words(index, vault, monkeypatch):
    monkeypatch.setattr(run_eval, "server", index)
    index.index_paths([str(vault)])
    top = run_eval.grep_search("water the tomatoes in july", 5)
    assert top[0][0].endswith("garden.md")
    assert run_eval.grep_search("zzz qqq", 5) == []


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


def test_session_sizes_counts_each_api_call_once(tmp_path):
    import session_sizes

    def call(mid, tokens):
        return json.dumps({"type": "assistant", "timestamp": "2026-10-27T10:00:00Z",
                           "message": {"id": mid, "usage": {"input_tokens": tokens}}})

    t = tmp_path / "t.jsonl"
    t.write_text("\n".join([call("a", 100), call("a", 100), call("b", 200), call("b", 200)]), encoding="utf-8")
    assert session_sizes.session(t) == ("2026-10-27", [100, 200])


def test_context_guard_is_silent_below_the_hard_limit_and_fires_above(tmp_path, monkeypatch, capsys):
    import io

    import context_guard

    monkeypatch.setattr(context_guard, "load_config", lambda: {"hard": 1000, "idle_min": 500, "idle_minutes": 60})
    t = tmp_path / "t.jsonl"
    for tokens, fires in ((999, False), (1000, True)):
        t.write_text(json.dumps({"message": {"usage": {"input_tokens": tokens}}}), encoding="utf-8")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": str(t)})))
        monkeypatch.setattr("sys.argv", ["context_guard.py"])
        assert context_guard.main() == 0
        out = capsys.readouterr().out
        assert ("hard limit" in out) is fires


def test_context_guard_fires_once_per_session_mid_turn(tmp_path, monkeypatch, capsys):
    import io

    import context_guard

    monkeypatch.setattr(context_guard, "load_config", lambda: {"hard": 1000, "idle_min": 500, "idle_minutes": 60})
    monkeypatch.setattr(context_guard, "STATE", tmp_path / "state")
    monkeypatch.setattr("sys.argv", ["context_guard.py"])
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"message": {"usage": {"input_tokens": 1500}}}), encoding="utf-8")
    event = {"transcript_path": str(t), "hook_event_name": "PostToolUse", "session_id": "s1"}
    outs = []
    for _ in range(2):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
        assert context_guard.main() == 0
        outs.append(capsys.readouterr().out)
    assert '"hookEventName": "PostToolUse"' in outs[0] and "mid-turn" in outs[0]
    assert outs[1] == ""


def test_abs_paths_expands_project_dir():
    root = invariants.ROOT.as_posix()
    cmd = 'uv run --project "$CLAUDE_PROJECT_DIR"/mcp python $CLAUDE_PROJECT_DIR/mcp/x.py --flag'
    assert invariants.abs_paths(cmd) == [f"{root}/mcp", f"{root}/mcp/x.py"]


def test_hook_check_flags_a_missing_script(tmp_path, monkeypatch):
    (tmp_path / ".claude").mkdir()
    (tmp_path / "mcp/.venv").mkdir(parents=True)
    hook = {"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR"/mcp/reindex_hook.py'}
    settings = {"hooks": {"PostToolUse": [{"hooks": [hook]}], "Stop": [{"hooks": [{**hook, "async": True}]}]}}
    (tmp_path / ".claude/settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(invariants, "ROOT", tmp_path)
    assert any("hook path missing" in p for p in invariants.check_hook())
    (tmp_path / "mcp/reindex_hook.py").write_text("", encoding="utf-8")
    assert invariants.check_hook() == []


def test_skill_listing_budget_reads_newest_listing_since_settings_change(tmp_path, monkeypatch):
    def listing(ts, content):
        return json.dumps({"type": "attachment", "timestamp": ts,
                           "attachment": {"type": "skill_listing", "content": content}})

    old, new, empty = tmp_path / "old.jsonl", tmp_path / "new.jsonl", tmp_path / "empty.jsonl"
    old.write_text(listing("2026-10-27T10:00:00Z", "x" * 40), encoding="utf-8")
    new.write_text("\n".join(['{"broken": ', listing("2026-10-28T10:00:00Z", "small"),
                              listing("2026-10-28T11:00:00Z", "y" * 400)]), encoding="utf-8")
    empty.write_text(json.dumps({"type": "user"}), encoding="utf-8")
    for f, t in ((old, 1), (new, 2), (empty, 3)):
        os.utime(f, (1_800_000_000 + t,) * 2)
    since = 1_800_000_000  # all files are newer; listings are dated 2026, before this time
    assert invariants.latest_skill_listing(tmp_path, since) is None
    assert invariants.latest_skill_listing(tmp_path, 0) == "y" * 400  # newest file with a listing, last listing

    monkeypatch.setattr(invariants, "TRANSCRIPTS", tmp_path)
    monkeypatch.setattr(invariants, "latest_skill_listing", lambda d, s: "z" * 4 * invariants.SKILL_LISTING_TOKEN_BUDGET)
    assert invariants.check_skill_listing() != []


def test_handoff_config_defaults_when_the_project_has_none(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff_common, "CONFIG", tmp_path / ".claude/handoff.json")
    assert handoff_common.load_config() == {"hard": handoff_common.DEFAULT_HARD,
                                            "idle_min": handoff_common.DEFAULT_IDLE_MIN,
                                            "idle_minutes": handoff_common.DEFAULT_IDLE_MINUTES}


def test_context_guard_offers_a_handoff_after_an_idle_gap(tmp_path, monkeypatch, capsys):
    import io
    from datetime import datetime, timedelta, timezone

    import context_guard

    monkeypatch.setattr(context_guard, "load_config", lambda: {"hard": 1000, "idle_min": 500, "idle_minutes": 60})
    monkeypatch.setattr("sys.argv", ["context_guard.py"])
    t = tmp_path / "t.jsonl"
    now = datetime.now(timezone.utc)
    cases = (  # (tokens, minutes since the last reply, event, offers a handoff)
        (600, 90, "UserPromptSubmit", True),
        (600, 10, "UserPromptSubmit", False),
        (400, 90, "UserPromptSubmit", False),
        (600, 90, "PostToolUse", False),
    )
    for tokens, minutes, name, fires in cases:
        ts = (now - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
        t.write_text(json.dumps({"type": "assistant", "timestamp": ts,
                                 "message": {"usage": {"input_tokens": tokens}}}), encoding="utf-8")
        event = {"transcript_path": str(t), "hook_event_name": name, "session_id": f"s{tokens}{minutes}"}
        monkeypatch.setattr(context_guard, "STATE", tmp_path / "state")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
        assert context_guard.main() == 0
        assert ("was idle for" in capsys.readouterr().out) is fires, (tokens, minutes, name)


def test_golden_hash_ignores_line_endings(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_bytes(b'{"id": 1}\n{"id": 2}\n')
    b.write_bytes(b'{"id": 1}\r\n{"id": 2}\r\n')
    assert run_eval.golden_sha256(a) == run_eval.golden_sha256(b)
    b.write_bytes(b'{"id": 1}\r\n{"id": 3}\r\n')
    assert run_eval.golden_sha256(a) != run_eval.golden_sha256(b)


def test_baseline_notes_warn_on_stale_hash_model_and_rises():
    scores = {"ndcg@5": 0.5, "mrr": 0.5, "recall@5": 0.5}
    base = {"date": "2026-10-24", "model": "m", "golden_sha256": "old", "scores": dict(scores)}
    assert run_eval.baseline_notes(base, "old", "m", scores) == []
    stale = run_eval.baseline_notes(base, "new", "m", scores)
    assert len(stale) == 1 and "baseline is stale: golden set changed since 2026-10-24" in stale[0]
    assert "no golden_sha256" in run_eval.baseline_notes({**base, "golden_sha256": None}, "new", "m", scores)[0]
    assert "model" in run_eval.baseline_notes(base, "old", "other", scores)[0]
    up = run_eval.baseline_notes(base, "old", "m", {**scores, "mrr": 0.6})
    assert len(up) == 1 and "mrr" in up[0] and "re-saved" in up[0]


def _pq(ndcg):
    return {"ndcg@5": ndcg, "mrr": 1.0, "recall@5": 1.0}


def test_question_moves_hint_when_baseline_has_no_per_question():
    out = run_eval.question_moves({"scores": {}}, {"q1": _pq(1.0)}, {"q1": "x"})
    assert len(out) == 1 and "no per_question" in out[0]


def test_question_moves_unchanged_is_silent():
    base = {"per_question": {"q1": _pq(0.5), "q2": _pq(1.0)}}
    assert run_eval.question_moves(base, {"q1": _pq(0.5005), "q2": _pq(1.0)}, {}) == []


def test_question_moves_lists_a_drop_with_truncated_text():
    base = {"per_question": {"q1": _pq(1.0), "q2": _pq(1.0)}}
    out = run_eval.question_moves(base, {"q1": _pq(0.5), "q2": _pq(1.0)}, {"q1": "w" * 100})
    assert len(out) == 1 and "q1" in out[0] and "1.000 -> 0.500" in out[0] and "w" * 100 not in out[0]


def test_question_moves_lists_new_and_removed_ids():
    base = {"per_question": {"old": _pq(0.7)}}
    out = run_eval.question_moves(base, {"fresh": _pq(0.9)}, {"fresh": "a question"})
    assert any("fresh new" in line for line in out) and any("old removed" in line for line in out)


def test_golden_check_fails_on_a_stale_baseline_hash(tmp_path, monkeypatch):
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval/golden.jsonl").write_bytes(b"")
    monkeypatch.setattr(invariants, "ROOT", tmp_path)
    base = tmp_path / "eval/baseline.json"
    base.write_text(json.dumps({"scores": {}}), encoding="utf-8")
    assert invariants.check_golden() == []  # no hash yet: passes until the next re-save
    base.write_text(json.dumps({"golden_sha256": "stale"}), encoding="utf-8")
    assert any("stale" in p for p in invariants.check_golden())
    base.write_text(json.dumps({"golden_sha256": run_eval.golden_sha256(tmp_path / "eval/golden.jsonl")}), encoding="utf-8")
    assert invariants.check_golden() == []


def test_hook_check_quotes_a_recent_log_entry_only(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    (tmp_path / ".claude").mkdir()
    (tmp_path / "mcp/.venv").mkdir(parents=True)
    (tmp_path / "mcp/reindex_hook.py").write_text("", encoding="utf-8")
    hook = {"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR"/mcp/reindex_hook.py'}
    settings = {"hooks": {"PostToolUse": [{"hooks": [hook]}], "Stop": [{"hooks": [{**hook, "async": True}]}]}}
    (tmp_path / ".claude/settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(invariants, "ROOT", tmp_path)
    monkeypatch.setattr(invariants, "INDEX_DB", tmp_path / "vault-index.db")
    log = tmp_path / "reindex-hook.log"
    old = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    log.write_text(f"{old} Stop OSError: old\n", encoding="utf-8")
    assert invariants.check_hook() == []
    new = datetime.now().isoformat(timespec="seconds")
    log.write_text(f"{old} Stop OSError: old\n{new} Stop OSError: fresh\n", encoding="utf-8")
    assert any("OSError: fresh" in p for p in invariants.check_hook())


def write_handoff(folder, name, status, date_line=True):
    folder.mkdir(exist_ok=True)
    head = "date: 2026-11-01\n" if date_line else ""
    (folder / name).write_text(f"---\n{head}status: {status}\n---\n\n# x\n", encoding="utf-8")


def test_stale_handoffs_flags_only_open_notes_over_seven_days(tmp_path):
    from datetime import date

    today = date(2026, 11, 17)
    h = tmp_path / "handoffs"
    assert invariants.stale_handoffs(h, today) == []  # no folder passes
    write_handoff(h, "a.md", "open")  # 16 days
    assert invariants.stale_handoffs(h, today) == ["a.md"]
    for status in ("parked", "picked-up", "closed"):
        (h / "a.md").unlink()
        write_handoff(h, "a.md", status)
        assert invariants.stale_handoffs(h, today) == []
    (h / "b.md").write_text("no frontmatter\n", encoding="utf-8")
    assert invariants.stale_handoffs(h, today) == []


def test_stale_handoffs_boundary_is_seven_days(tmp_path):
    from datetime import date

    h = tmp_path / "handoffs"
    write_handoff(h, "a.md", "open")  # dated 2026-11-01
    assert invariants.stale_handoffs(h, date(2026, 11, 8)) == []  # 7 days old
    assert invariants.stale_handoffs(h, date(2026, 11, 9)) == ["a.md"]  # 8 days old


def test_stale_handoffs_date_falls_back_to_file_name(tmp_path):
    from datetime import date

    h = tmp_path / "handoffs"
    write_handoff(h, "2026-11-01-topic.md", "open", date_line=False)
    assert invariants.stale_handoffs(h, date(2026, 11, 17)) == ["2026-11-01-topic.md"]
    assert invariants.stale_handoffs(h, date(2026, 11, 5)) == []
