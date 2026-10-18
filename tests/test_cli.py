from datetime import date, timedelta

from todo_app.cli import run


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
        "error: unknown command 'prio'",
        "error: unknown command '1'",
        "error: unknown command 'high'",
    ]
