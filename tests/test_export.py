from datetime import date

import pytest

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
        render([], "json")
