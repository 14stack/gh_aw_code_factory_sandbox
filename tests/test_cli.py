import json
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


def test_missing_id_reports_error():
    assert run(["done"]) == ["error: missing id"]
    assert run(["rm"]) == ["error: missing id"]
    assert run(["add", "milk", "done", "list"]) == [
        "added 1: milk",
        "error: missing id",
        "[ ] 1: milk",
    ]


def test_valid_and_unknown_ids_unchanged():
    assert run(["add", "milk", "done", "1", "rm", "5"]) == [
        "added 1: milk",
        "done 1",
        "error: no todo 5",
    ]


def test_invalid_id_reports_error_and_continues():
    assert run(["done", "abc", "list"]) == ["error: invalid id 'abc'"]
    assert run(["add", "milk", "done", "abc", "list"]) == [
        "added 1: milk",
        "error: invalid id 'abc'",
        "[ ] 1: milk",
    ]


def test_invalid_rm_id_reports_error():
    assert run(["add", "milk", "rm", "x", "list"]) == [
        "added 1: milk",
        "error: invalid id 'x'",
        "[ ] 1: milk",
    ]


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


def test_cli_persists_priority_between_runs(tmp_path):
    path = tmp_path / "todos.json"
    assert run(["add", "pay rent", "priority", "high"], TodoStore(path=path)) == [
        "added 1: pay rent"
    ]
    assert run(["list"], TodoStore(path=path)) == ["! [ ] 1: pay rent"]

    assert run(["add", "tidy desk", "priority", "low"], TodoStore(path=path)) == [
        "added 2: tidy desk"
    ]
    assert run(["list"], TodoStore(path=path)) == ["! [ ] 1: pay rent", "↓ [ ] 2: tidy desk"]


def test_cli_persists_prio_change_between_runs(tmp_path):
    path = tmp_path / "todos.json"
    assert run(["add", "pay rent", "prio", "1", "high"], TodoStore(path=path)) == [
        "added 1: pay rent",
        "prio 1: high",
    ]
    assert run(["list"], TodoStore(path=path)) == ["! [ ] 1: pay rent"]

    assert run(["add", "tidy desk", "done", "2", "prio", "2", "high"], TodoStore(path=path)) == [
        "added 2: tidy desk",
        "done 2",
        "prio 2: high",
    ]
    assert run(["list"], TodoStore(path=path)) == ["! [ ] 1: pay rent", "! [x] 2: tidy desk"]


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


def test_cli_reports_invalid_priority_in_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "todos.json"
    document = json.dumps(
        {
            "version": 1,
            "next_id": 2,
            "todos": [
                {
                    "id": 1,
                    "title": "pay rent",
                    "done": False,
                    "recurrence": None,
                    "due": None,
                    "priority": "urgent",
                }
            ],
        }
    )
    path.write_text(document, encoding="utf-8")
    monkeypatch.setenv("TODO_FILE", str(path))
    monkeypatch.setattr(sys, "argv", ["todo", "list"])

    assert main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"error: cannot read {path}:" in captured.err
    assert "todo 1: invalid priority 'urgent'" in captured.err
    assert path.read_text(encoding="utf-8") == document


def test_add_with_priority_and_list_marks_high_and_low():
    assert run(
        [
            "add",
            "pay rent",
            "priority",
            "high",
            "add",
            "tidy desk",
            "priority",
            "low",
            "add",
            "milk",
            "list",
        ]
    ) == [
        "added 1: pay rent",
        "added 2: tidy desk",
        "added 3: milk",
        "! [ ] 1: pay rent",
        "[ ] 3: milk",
        "↓ [ ] 2: tidy desk",
    ]


def test_priority_combines_with_every_and_due_in_any_order():
    future = date.today() + timedelta(days=7)
    expected = [
        "added 1: water plants",
        f"! [ ] 1: water plants (every 3d) (due {future.isoformat()})",
    ]
    assert (
        run(
            [
                "add",
                "water plants",
                "priority",
                "high",
                "every",
                "3d",
                "due",
                str(future),
                "list",
            ]
        )
        == expected
    )
    assert (
        run(
            [
                "add",
                "water plants",
                "due",
                str(future),
                "every",
                "3d",
                "priority",
                "high",
                "list",
            ]
        )
        == expected
    )


def test_list_orders_high_medium_low():
    assert run(
        [
            "add",
            "low one",
            "priority",
            "low",
            "add",
            "medium one",
            "add",
            "high one",
            "priority",
            "high",
            "list",
        ]
    ) == [
        "added 1: low one",
        "added 2: medium one",
        "added 3: high one",
        "! [ ] 3: high one",
        "[ ] 2: medium one",
        "↓ [ ] 1: low one",
    ]


def test_invalid_priority_rejected():
    assert run(["add", "x", "priority", "urgent", "list"]) == [
        "error: invalid priority 'urgent'",
    ]
    assert run(["add", "x", "priority", "list"]) == [
        "error: invalid priority 'list'",
    ]
    assert run(["add", "x", "priority"]) == ["error: invalid priority ''"]


def test_due_does_not_swallow_prio_command():
    # ``prio`` is a command keyword, so ``due`` reports a missing date and leaves it as a command.
    assert run(["add", "x", "due", "prio", "1", "high"]) == [
        "error: invalid due date ''",
        "error: no todo 1",
    ]


def test_prio_changes_priority():
    assert run(["add", "pay rent", "prio", "1", "high", "list"]) == [
        "added 1: pay rent",
        "prio 1: high",
        "! [ ] 1: pay rent",
    ]


def test_prio_errors():
    assert run(["prio", "7", "high"]) == ["error: no todo 7"]
    assert run(["add", "x", "prio", "1", "urgent", "list"]) == [
        "added 1: x",
        "error: invalid priority 'urgent'",
        "[ ] 1: x",
    ]
    # ``list`` is consumed as the level, matching ``add x priority list``.
    assert run(["add", "x", "prio", "1", "list"]) == [
        "added 1: x",
        "error: invalid priority 'list'",
    ]
    assert run(["add", "x", "prio", "1"]) == [
        "added 1: x",
        "error: invalid priority ''",
    ]


def test_prio_invalid_id_reports_error_and_continues():
    assert run(["prio", "abc", "high"]) == ["error: invalid id 'abc'"]
    assert run(["add", "milk", "prio", "abc", "high", "list"]) == [
        "added 1: milk",
        "error: invalid id 'abc'",
        "[ ] 1: milk",
    ]
    assert run(["prio", "1.5", "high"]) == ["error: invalid id '1.5'"]


def test_prio_invalid_id_leaves_following_command():
    assert run(["add", "milk", "prio", "abc", "list"]) == [
        "added 1: milk",
        "error: invalid id 'abc'",
        "[ ] 1: milk",
    ]


def test_prio_missing_id_reports_error():
    assert run(["prio"]) == ["error: missing id"]
    assert run(["add", "milk", "prio", "list"]) == [
        "added 1: milk",
        "error: missing id",
        "[ ] 1: milk",
    ]


def test_prio_works_on_completed_todos():
    assert run(["add", "x", "done", "1", "prio", "1", "high", "list"]) == [
        "added 1: x",
        "done 1",
        "prio 1: high",
        "! [x] 1: x",
    ]


def test_list_filters_by_priority():
    assert run(
        [
            "add",
            "low one",
            "priority",
            "low",
            "add",
            "medium one",
            "add",
            "high one",
            "priority",
            "high",
            "add",
            "high two",
            "priority",
            "high",
            "list",
            "high",
        ]
    ) == [
        "added 1: low one",
        "added 2: medium one",
        "added 3: high one",
        "added 4: high two",
        "! [ ] 3: high one",
        "! [ ] 4: high two",
    ]
    assert run(
        [
            "add",
            "low one",
            "priority",
            "low",
            "add",
            "medium one",
            "add",
            "high one",
            "priority",
            "high",
            "list",
            "low",
        ]
    ) == [
        "added 1: low one",
        "added 2: medium one",
        "added 3: high one",
        "↓ [ ] 1: low one",
    ]


def test_list_invalid_filter_rejected():
    assert run(["add", "x", "list", "urgent"]) == [
        "added 1: x",
        "error: invalid filter 'urgent'",
    ]


def test_list_filters_by_status():
    past = date.today() - timedelta(days=1)
    setup = ["add", "open one", "add", "done one", "done", "2", "add", "late", "due", str(past)]
    assert run([*setup, "list", "open"]) == [
        "added 1: open one",
        "added 2: done one",
        "done 2",
        "added 3: late",
        f"[ ] 3: late (due {past.isoformat()}, OVERDUE)",
        "[ ] 1: open one",
    ]
    assert run([*setup, "list", "done"]) == [
        "added 1: open one",
        "added 2: done one",
        "done 2",
        "added 3: late",
        "[x] 2: done one",
    ]
    assert run([*setup, "list", "overdue"]) == [
        "added 1: open one",
        "added 2: done one",
        "done 2",
        "added 3: late",
        f"[ ] 3: late (due {past.isoformat()}, OVERDUE)",
    ]


def test_list_combines_status_and_priority_in_either_order():
    setup = [
        "add",
        "a",
        "priority",
        "high",
        "add",
        "b",
        "priority",
        "high",
        "done",
        "2",
        "add",
        "c",
    ]
    expected = [
        "added 1: a",
        "added 2: b",
        "done 2",
        "added 3: c",
        "! [ ] 1: a",
    ]
    assert run([*setup, "list", "open", "high"]) == expected
    assert run([*setup, "list", "high", "open"]) == expected


def test_list_invalid_filter_continues_chain():
    assert run(["add", "a", "list", "bogus", "count"]) == [
        "added 1: a",
        "error: invalid filter 'bogus'",
        "open 1, done 0",
    ]


def test_list_repeated_status_or_priority_rejected():
    setup = ["add", "a", "priority", "high", "add", "b", "priority", "low", "done", "2"]
    assert run([*setup, "list", "open", "done", "count"]) == [
        "added 1: a",
        "added 2: b",
        "done 2",
        "error: invalid filter 'done'",
        "open 1, done 1",
    ]
    assert run([*setup, "list", "high", "low", "count"]) == [
        "added 1: a",
        "added 2: b",
        "done 2",
        "error: invalid filter 'low'",
        "open 1, done 1",
    ]


def test_list_done_with_number_reports_invalid_filter():
    assert run(["add", "a", "done", "1", "list", "done", "1"]) == [
        "added 1: a",
        "done 1",
        "error: invalid filter '1'",
    ]


def test_list_leaves_following_command_keyword():
    assert run(["add", "a", "add", "b", "done", "1", "list", "count"]) == [
        "added 1: a",
        "added 2: b",
        "done 1",
        "[x] 1: a",
        "[ ] 2: b",
        "open 1, done 1",
    ]


def test_export_defaults_to_markdown():
    assert run(["add", "milk", "add", "spec", "done", "1", "export"]) == [
        "added 1: milk",
        "added 2: spec",
        "done 1",
        "- [x] 1: milk",
        "- [ ] 2: spec",
    ]


def test_export_explicit_markdown():
    assert run(["add", "milk", "export", "md"]) == [
        "added 1: milk",
        "- [ ] 1: milk",
    ]


def test_export_csv():
    assert run(["add", "milk", "export", "csv"]) == [
        "added 1: milk",
        "id,title,done,recurrence,due,priority",
        "1,milk,false,,,medium",
    ]


def test_export_json():
    assert run(["add", "milk", "export", "json"]) == [
        "added 1: milk",
        '{"version": 1, "next_id": 2, "todos": ['
        '{"id": 1, "title": "milk", "done": false, "recurrence": null, '
        '"due": null, "priority": "medium"}]}',
    ]


def test_export_json_in_a_command_chain():
    assert run(["add", "milk", "done", "1", "export", "json", "count"]) == [
        "added 1: milk",
        "done 1",
        '{"version": 1, "next_id": 2, "todos": ['
        '{"id": 1, "title": "milk", "done": true, "recurrence": null, '
        '"due": null, "priority": "medium"}]}',
        "open 0, done 1",
    ]


def test_export_invalid_format_continues_chain():
    assert run(["add", "milk", "export", "xml", "count"]) == [
        "added 1: milk",
        "error: invalid format 'xml'",
        "open 1, done 0",
    ]


def test_export_does_not_swallow_following_command():
    assert run(["add", "milk", "export", "count"]) == [
        "added 1: milk",
        "- [ ] 1: milk",
        "open 1, done 0",
    ]


def test_export_is_not_taken_as_due_date():
    # ``export`` is a command keyword, so ``due`` reports a missing date and leaves it as a command.
    assert run(["add", "milk", "due", "export", "count"]) == [
        "error: invalid due date ''",
        "open 0, done 0",
    ]


def test_export_on_empty_store():
    assert run(["export"]) == []
    assert run(["export", "csv"]) == ["id,title,done,recurrence,due,priority"]
    assert run(["export", "json"]) == ['{"version": 1, "next_id": 1, "todos": []}']


def test_due_sets_iso_date_and_relative_and_none():
    store = TodoStore()
    assert run(["add", "milk"], store) == ["added 1: milk"]
    assert run(["due", "1", "2026-11-01", "list"], store) == [
        "[ ] 1: milk (due 2026-11-01)",
        "[ ] 1: milk (due 2026-11-01)",
    ]
    assert run(["due", "1", "+3d"], store) == [
        f"[ ] 1: milk (due {date.today() + timedelta(days=3)})",
    ]
    assert run(["due", "1", "none", "list"], store) == [
        "[ ] 1: milk",
        "[ ] 1: milk",
    ]


def test_due_errors():
    assert run(["due", "7", "2026-11-01"]) == ["error: no todo 7"]
    store = TodoStore()
    assert run(["add", "x"], store) == ["added 1: x"]
    assert run(["due", "1", "tomorrow", "list"], store) == [
        "error: invalid due date 'tomorrow'",
        "[ ] 1: x",
    ]
    assert run(["due", "1", "+0d"], store) == ["error: invalid due date '+0d'"]
    assert run(["due", "1"], store) == ["error: invalid due date ''"]


def test_due_invalid_id_reports_error_and_continues():
    assert run(["due", "abc", "2026-11-01"]) == ["error: invalid id 'abc'"]
    store = TodoStore()
    assert run(["add", "milk"], store) == ["added 1: milk"]
    assert run(["due", "abc", "2026-11-01", "list"], store) == [
        "error: invalid id 'abc'",
        "[ ] 1: milk",
    ]


def test_find_matches_case_insensitively():
    assert run(["add", "buy MILK", "add", "write spec", "find", "milk"]) == [
        "added 1: buy MILK",
        "added 2: write spec",
        "[ ] 1: buy MILK",
    ]


def test_find_includes_done_todos():
    assert run(["add", "buy milk", "add", "write spec", "done", "1", "find", "milk"]) == [
        "added 1: buy milk",
        "added 2: write spec",
        "done 1",
        "[x] 1: buy milk",
    ]


def test_find_no_match_prints_nothing():
    assert run(["add", "buy milk", "find", "spec"]) == ["added 1: buy milk"]
    assert run(["find", "anything"]) == []


def test_find_without_text_reports_error():
    assert run(["find"]) == ["error: missing text"]
    assert run(["add", "milk", "find", "list"]) == [
        "added 1: milk",
        "error: missing text",
        "[ ] 1: milk",
    ]


def test_due_missing_id_reports_error():
    assert run(["due"]) == ["error: missing id"]
    store = TodoStore()
    assert run(["add", "milk"], store) == ["added 1: milk"]
    assert run(["due", "list"], store) == ["error: missing id", "[ ] 1: milk"]


def test_due_keeps_recurrence():
    store = TodoStore()
    assert run(["add", "water", "every", "3d"], store) == ["added 1: water"]
    assert run(["due", "1", "2026-11-01", "list"], store) == [
        "[ ] 1: water (every 3d) (due 2026-11-01)",
        "[ ] 1: water (every 3d) (due 2026-11-01)",
    ]
    assert run(["due", "1", "none", "list"], store) == [
        "[ ] 1: water (every 3d)",
        "[ ] 1: water (every 3d)",
    ]


def test_due_does_not_swallow_list_command():
    store = TodoStore()
    assert run(["add", "x"], store) == ["added 1: x"]
    assert run(["due", "1", "list"], store) == ["error: invalid due date 'list'"]


def test_cli_persists_due_change_between_runs(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    run(["add", "milk"], store)
    run(["due", "1", "2026-11-01"], store)
    reloaded = TodoStore(path)
    assert reloaded.get(1).due == date(2026, 11, 1)
    run(["due", "1", "none"], reloaded)
    assert TodoStore(path).get(1).due is None


def test_find_output_matches_list_lines():
    future = date.today() + timedelta(days=7)
    out = run(
        [
            "add",
            "water plants",
            "priority",
            "high",
            "due",
            str(future),
            "add",
            "write spec",
            "done",
            "1",
            "list",
            "find",
            "water",
        ]
    )
    assert out[-1] == f"! [x] 1: water plants (due {future.isoformat()})"
    assert out[-1] == out[3]


def test_find_chains_with_following_command():
    assert run(["add", "buy milk", "add", "write spec", "find", "milk", "count"]) == [
        "added 1: buy milk",
        "added 2: write spec",
        "[ ] 1: buy milk",
        "open 2, done 0",
    ]


def test_find_keyword_as_text_is_missing_text():
    assert run(["add", "milk", "find", "list", "count"]) == [
        "added 1: milk",
        "error: missing text",
        "[ ] 1: milk",
        "open 1, done 0",
    ]


def test_undo_reopens_done_todo():
    assert run(["add", "milk", "done", "1", "undo", "1", "list"]) == [
        "added 1: milk",
        "done 1",
        "reopened 1",
        "[ ] 1: milk",
    ]


def test_undo_open_todo_stays_open():
    assert run(["add", "milk", "undo", "1", "list"]) == [
        "added 1: milk",
        "reopened 1",
        "[ ] 1: milk",
    ]


def test_undo_missing_id_reports_error():
    assert run(["undo"]) == ["error: missing id"]
    assert run(["add", "milk", "undo", "list"]) == [
        "added 1: milk",
        "error: missing id",
        "[ ] 1: milk",
    ]


def test_undo_invalid_id_reports_error_and_continues():
    assert run(["undo", "x", "list"]) == ["error: invalid id 'x'"]


def test_undo_unknown_id_reports_error():
    assert run(["undo", "99"]) == ["error: no todo 99"]


def test_undo_keyword_is_command():
    assert run(["add", "milk", "done", "1", "undo", "list"]) == [
        "added 1: milk",
        "done 1",
        "error: missing id",
        "[x] 1: milk",
    ]


def test_show_prints_list_format_line():
    assert run(["add", "milk", "show", "1"]) == [
        "added 1: milk",
        "[ ] 1: milk",
    ]


def test_show_prints_done_todo():
    assert run(["add", "milk", "done", "1", "show", "1"]) == [
        "added 1: milk",
        "done 1",
        "[x] 1: milk",
    ]


def test_show_prints_priority_markers():
    assert run(["add", "urgent", "priority", "high", "show", "1"]) == [
        "added 1: urgent",
        "! [ ] 1: urgent",
    ]
    assert run(["add", "later", "priority", "low", "show", "1"]) == [
        "added 1: later",
        "↓ [ ] 1: later",
    ]


def test_show_prints_recurrence_and_due_suffixes():
    future = date.today() + timedelta(days=7)
    past = date.today() - timedelta(days=1)
    assert run(["add", "water plants", "every", "3d", "show", "1"]) == [
        "added 1: water plants",
        "[ ] 1: water plants (every 3d)",
    ]
    assert run(["add", "milk", "due", str(future), "show", "1"]) == [
        "added 1: milk",
        f"[ ] 1: milk (due {future.isoformat()})",
    ]
    assert run(["add", "old", "due", str(past), "show", "1"]) == [
        "added 1: old",
        f"[ ] 1: old (due {past.isoformat()}, OVERDUE)",
    ]


def test_show_matches_list_line():
    future = date.today() + timedelta(days=7)
    args = ["add", "water plants", "every", "weekly", "due", str(future), "priority", "high"]
    assert run([*args, "show", "1"]) == run([*args, "list"])


def test_show_missing_id_reports_error():
    assert run(["show"]) == ["error: missing id"]
    assert run(["add", "milk", "show", "list"]) == [
        "added 1: milk",
        "error: missing id",
        "[ ] 1: milk",
    ]


def test_show_invalid_id_reports_error_and_continues():
    assert run(["show", "abc", "count"]) == [
        "error: invalid id 'abc'",
        "open 0, done 0",
    ]


def test_show_unknown_id_reports_error_and_continues():
    assert run(["add", "milk", "show", "99", "list"]) == [
        "added 1: milk",
        "error: no todo 99",
        "[ ] 1: milk",
    ]


def test_show_is_not_a_list_filter():
    assert run(["add", "milk", "list", "show"]) == [
        "added 1: milk",
        "[ ] 1: milk",
        "error: missing id",
    ]
