import sys
from datetime import date, timedelta

from todo_app.cli import main, run
from todo_app.store import TodoStore


def test_add_done_list():
    assert run(["add", "milk", "add", "spec", "done", "1", "list"]) == [
        "added 1: milk",
        "added 2: spec",
        "done 1",
        "[x] 1: milk",
        "[ ] 2: spec",
    ]


def test_errors_are_reported():
    assert run(["done", "7", "bogus"]) == [
        "error: no todo 7",
        "error: unknown command 'bogus'",
    ]


def test_add_recurring_and_list():
    assert run(["add", "water plants", "every", "3d", "list"]) == [
        "added 1: water plants",
        "[ ] 1: water plants (every 3d)",
    ]


def test_weekly_interval_renders_as_weekly():
    assert run(["add", "water plants", "every", "weekly", "list"]) == [
        "added 1: water plants",
        "[ ] 1: water plants (weekly)",
    ]


def test_done_recurring_spawns_and_lists():
    assert run(["add", "water plants", "every", "3d", "done", "1", "list"]) == [
        "added 1: water plants",
        "done 1",
        "[x] 1: water plants (every 3d)",
        "[ ] 2: water plants (every 3d)",
    ]


def test_invalid_intervals_are_rejected():
    assert run(["add", "water plants", "every", "0d", "list"]) == [
        "error: invalid interval '0d'",
    ]
    assert run(["add", "water plants", "every", "fortnight", "list"]) == [
        "error: invalid interval 'fortnight'",
    ]


def test_add_due_and_list_shows_due_suffix():
    future = date.today() + timedelta(days=7)
    assert run(["add", "milk", "due", str(future), "list"]) == [
        "added 1: milk",
        f"[ ] 1: milk (due {future.isoformat()})",
    ]


def test_list_orders_dated_first():
    future = date.today() + timedelta(days=7)
    assert run(["add", "undated", "add", "dated", "due", str(future), "list"]) == [
        "added 1: undated",
        "added 2: dated",
        f"[ ] 2: dated (due {future.isoformat()})",
        "[ ] 1: undated",
    ]


def test_invalid_due_date_rejected():
    assert run(["add", "x", "due", "not-a-date", "list"]) == [
        "error: invalid due date 'not-a-date'",
    ]


def test_missing_due_token_rejected():
    assert run(["add", "x", "due", "list"]) == [
        "error: invalid due date ''",
    ]
    assert run(["add", "x", "due"]) == ["error: invalid due date ''"]


def test_past_due_marks_overdue():
    past = date.today() - timedelta(days=1)
    today = date.today()
    future = date.today() + timedelta(days=1)
    assert run(["add", "past", "due", str(past), "list"]) == [
        "added 1: past",
        f"[ ] 1: past (due {past.isoformat()}, OVERDUE)",
    ]
    assert run(["add", "today", "due", str(today), "list"]) == [
        "added 1: today",
        f"[ ] 1: today (due {today.isoformat()})",
    ]
    assert run(["add", "future", "due", str(future), "list"]) == [
        "added 1: future",
        f"[ ] 1: future (due {future.isoformat()})",
    ]


def test_recurrence_and_due_together():
    future = date.today() + timedelta(days=7)
    expected = [
        "added 1: water plants",
        f"[ ] 1: water plants (every 3d) (due {future.isoformat()})",
    ]
    assert run(["add", "water plants", "every", "3d", "due", str(future), "list"]) == expected
    assert run(["add", "water plants", "due", str(future), "every", "3d", "list"]) == expected


def test_clear_chains_with_done_and_list():
    assert run(["add", "a", "add", "b", "done", "1", "clear", "list"]) == [
        "added 1: a",
        "added 2: b",
        "done 1",
        "cleared 1",
        "[ ] 2: b",
    ]


def test_clear_on_empty_store_prints_cleared_zero():
    assert run(["clear"]) == ["cleared 0"]


def test_clear_after_due_is_command_not_due_date():
    out = run(["add", "x", "due", "clear", "list"])
    assert out == ["error: invalid due date ''", "cleared 0"]
    assert "error: invalid due date 'clear'" not in out


def test_clear_removes_done_recurring_todo():
    assert run(["add", "water plants", "every", "3d", "done", "1", "clear", "list"]) == [
        "added 1: water plants",
        "done 1",
        "cleared 1",
        "[ ] 2: water plants (every 3d)",
    ]


def test_count_command():
    assert run(["add", "a", "add", "b", "done", "1", "count"]) == [
        "added 1: a",
        "added 2: b",
        "done 1",
        "open 1, done 1",
    ]


def test_count_on_empty_store():
    assert run(["count"]) == ["open 0, done 0"]


def test_count_chains_with_other_commands():
    assert run(["add", "a", "add", "b", "done", "1", "count", "list"]) == [
        "added 1: a",
        "added 2: b",
        "done 1",
        "open 1, done 1",
        "[x] 1: a",
        "[ ] 2: b",
    ]


def test_cli_persists_between_runs(tmp_path):
    path = tmp_path / "todos.json"
    assert run(["add", "buy milk"], TodoStore(path=path)) == ["added 1: buy milk"]
    assert run(["list"], TodoStore(path=path)) == ["[ ] 1: buy milk"]
    assert run(["count"], TodoStore(path=path)) == ["open 1, done 0"]


def test_cli_reports_unreadable_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "todos.json"
    corrupt = "{not json"
    path.write_text(corrupt, encoding="utf-8")
    monkeypatch.setenv("TODO_FILE", str(path))
    monkeypatch.setattr(sys, "argv", ["todo", "add", "buy milk"])

    assert main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"error: cannot read {path}:" in captured.err
    assert path.read_text(encoding="utf-8") == corrupt
