from datetime import date

import pytest

from todo_app import storage
from todo_app.export import render
from todo_app.store import Todo, TodoStore


def test_markdown_renders_open_and_done_todos():
    todos = [
        Todo(id=1, title="milk", due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", priority="high"),
        Todo(id=3, title="weekly review", recurrence="weekly", priority="low"),
    ]
    assert render(todos) == [
        "- [ ] 1: milk (due 2026-01-31)",
        "- [x] 2: water plants (every 3d)",
        "- [ ] 3: weekly review (weekly)",
    ]


def test_markdown_omits_priority_markers_and_overdue():
    todos = [Todo(id=1, title="pay rent", due=date(2000, 1, 1), priority="high")]
    assert render(todos, "md") == ["- [ ] 1: pay rent (due 2000-01-01)"]


def test_markdown_keeps_titles_verbatim():
    todos = [Todo(id=1, title='milk, eggs "fresh"')]
    assert render(todos) == ['- [ ] 1: milk, eggs "fresh"']


def test_csv_renders_header_and_rows():
    todos = [
        Todo(id=1, title="milk", due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", priority="high"),
    ]
    assert render(todos, "csv") == [
        "id,title,done,recurrence,due,priority",
        "1,milk,false,,2026-01-31,medium",
        "2,water plants,true,3d,,high",
    ]


def test_csv_quotes_titles_with_commas_and_quotes():
    todos = [Todo(id=1, title="milk, eggs"), Todo(id=2, title='say "hi"')]
    assert render(todos, "csv") == [
        "id,title,done,recurrence,due,priority",
        '1,"milk, eggs",false,,,medium',
        '2,"say ""hi""",false,,,medium',
    ]


def test_empty_store_renders_no_markdown_lines():
    assert render([], "md") == []


def test_empty_store_renders_csv_header_only():
    assert render([], "csv") == ["id,title,done,recurrence,due,priority"]


def test_render_follows_store_list_order():
    store = TodoStore()
    store.add("undated")
    store.add("dated", due=date(2026, 1, 31))
    store.add("urgent", priority="high")
    assert render(store.list()) == [
        "- [ ] 3: urgent",
        "- [ ] 2: dated (due 2026-01-31)",
        "- [ ] 1: undated",
    ]


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        render([], "xml")


def test_json_renders_one_line_document():
    todos = [
        Todo(id=1, title="milk", due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", priority="high"),
        Todo(id=3, title="weekly review", recurrence="weekly", priority="low"),
    ]
    assert render(todos, "json", next_id=4) == [
        '{"version": 1, "next_id": 4, "todos": ['
        '{"id": 1, "title": "milk", "done": false, "recurrence": null, '
        '"due": "2026-01-31", "priority": "medium", "tags": []}, '
        '{"id": 2, "title": "water plants", "done": true, "recurrence": "3d", '
        '"due": null, "priority": "high", "tags": []}, '
        '{"id": 3, "title": "weekly review", "done": false, "recurrence": "weekly", '
        '"due": null, "priority": "low", "tags": []}]}'
    ]


def test_json_empty_store_renders_empty_todos():
    assert render([], "json", next_id=1) == ['{"version": 1, "next_id": 1, "todos": []}']


def test_json_round_trips_through_storage_load(tmp_path):
    store = TodoStore()
    store.add("milk", due=date(2026, 1, 31))
    store.add("water plants", recurrence="3d", priority="high")
    store.complete(2)

    path = tmp_path / "todos.json"
    path.write_text(render(store.list(), "json", next_id=store.next_id)[0], encoding="utf-8")

    todos, next_id = storage.load(path)
    assert next_id == store.next_id
    assert todos == {todo.id: todo for todo in store.list()}


def test_markdown_and_csv_ignore_tags():
    todos = [Todo(id=1, title="milk", tags=("home", "shopping"))]
    assert render(todos, "md") == ["- [ ] 1: milk"]
    assert render(todos, "csv") == [
        "id,title,done,recurrence,due,priority",
        "1,milk,false,,,medium",
    ]


def test_json_includes_tags():
    todos = [Todo(id=1, title="milk", tags=("home", "shopping"))]
    assert render(todos, "json", next_id=2) == [
        '{"version": 1, "next_id": 2, "todos": ['
        '{"id": 1, "title": "milk", "done": false, "recurrence": null, '
        '"due": null, "priority": "medium", "tags": ["home", "shopping"]}]}'
    ]
