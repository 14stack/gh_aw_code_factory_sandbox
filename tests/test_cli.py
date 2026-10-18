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
