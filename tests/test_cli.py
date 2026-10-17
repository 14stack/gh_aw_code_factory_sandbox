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
