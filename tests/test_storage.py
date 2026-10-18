import json
from datetime import date
from pathlib import Path

import pytest

from todo_app import StorageError, Todo
from todo_app.storage import default_path, document, load, save


def test_default_path_uses_todo_file_env(monkeypatch, tmp_path):
    target = tmp_path / "custom.json"
    monkeypatch.setenv("TODO_FILE", str(target))
    assert default_path() == target


def test_default_path_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("TODO_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_path() == tmp_path / ".todo" / "todos.json"


def test_load_missing_file_returns_empty(tmp_path):
    path = tmp_path / "todos.json"
    assert load(path) == ({}, 1)
    assert not path.exists()


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "todos.json"
    todos = [
        Todo(id=1, title="milk", done=False, recurrence=None, due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", due=None),
        Todo(id=3, title="weekly review", done=False, recurrence="weekly", due=None),
    ]
    save(path, todos, next_id=4)

    loaded, next_id = load(path)
    assert next_id == 4
    assert loaded == {todo.id: todo for todo in todos}


def test_save_writes_versioned_document(tmp_path):
    path = tmp_path / "todos.json"
    save(path, [Todo(id=1, title="milk", due=date(2026, 1, 31))], next_id=2)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {
        "version": 1,
        "next_id": 2,
        "todos": [
            {
                "id": 1,
                "title": "milk",
                "done": False,
                "recurrence": None,
                "due": "2026-01-31",
                "priority": "medium",
            }
        ],
    }
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_save_writes_priority(tmp_path):
    path = tmp_path / "todos.json"
    save(
        path,
        [
            Todo(id=1, title="pay rent", priority="high"),
            Todo(id=2, title="tidy desk", priority="low"),
        ],
        next_id=3,
    )

    document = json.loads(path.read_text(encoding="utf-8"))
    assert [todo["priority"] for todo in document["todos"]] == ["high", "low"]


def test_load_defaults_missing_priority_to_medium(tmp_path):
    path = tmp_path / "todos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "next_id": 3,
                "todos": [
                    {"id": 1, "title": "a", "done": False, "recurrence": None, "due": None},
                    {"id": 2, "title": "b", "done": True, "recurrence": "3d", "due": None},
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded, _ = load(path)
    assert [todo.priority for todo in loaded.values()] == ["medium", "medium"]

    save(path, loaded.values(), next_id=3)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert [todo["priority"] for todo in document["todos"]] == ["medium", "medium"]


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "todos.json"
    save(path, [Todo(id=1, title="a")], next_id=2)
    save(path, [Todo(id=1, title="b")], next_id=2)

    assert [p.name for p in tmp_path.iterdir()] == ["todos.json"]
    loaded, _ = load(path)
    assert loaded[1].title == "b"


def test_save_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "deeper" / "todos.json"
    save(path, [Todo(id=1, title="a")], next_id=2)
    assert path.is_file()


def test_load_rejects_corrupt_json(tmp_path):
    path = tmp_path / "todos.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError):
        load(path)


def test_load_rejects_invalid_utf8(tmp_path):
    path = tmp_path / "todos.json"
    path.write_bytes(b'{"version": 1, "next_id": 1, "todos": [{"id": 1, "title": "caf\xe9"}]}')
    with pytest.raises(StorageError):
        load(path)


def test_save_wraps_parent_directory_errors(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(StorageError):
        save(blocker / "todos.json", [Todo(id=1, title="a")], next_id=2)


@pytest.mark.parametrize(
    "document",
    [
        {"next_id": 1, "todos": []},
        {"version": 2, "next_id": 1, "todos": []},
        {"version": 1, "next_id": "1", "todos": []},
        {"version": 1, "next_id": 1, "todos": {}},
        {"version": 1, "next_id": 1, "todos": [{"id": 1, "title": "a", "done": False}]},
        {"version": 1, "next_id": 1, "todos": [{"id": "1", "title": "a", "done": False}]},
        {"version": 1, "next_id": 1, "todos": [{"id": 1, "title": 2, "done": False}]},
        {"version": 1, "next_id": 1, "todos": [{"id": 1, "title": "a", "done": "no"}]},
        {
            "version": 1,
            "next_id": 1,
            "todos": [{"id": 1, "title": "a", "done": False, "recurrence": 3}],
        },
        {
            "version": 1,
            "next_id": 1,
            "todos": [{"id": 1, "title": "a", "done": False, "due": "not-a-date"}],
        },
        {
            "version": 1,
            "next_id": 1,
            "todos": [{"id": 1, "title": "a", "done": False, "due": 20260131}],
        },
        {
            "version": 1,
            "next_id": 1,
            "todos": [
                {
                    "id": 1,
                    "title": "a",
                    "done": False,
                    "recurrence": None,
                    "due": None,
                    "priority": "urgent",
                }
            ],
        },
        {
            "version": 1,
            "next_id": 1,
            "todos": [
                {
                    "id": 1,
                    "title": "a",
                    "done": False,
                    "recurrence": None,
                    "due": None,
                    "priority": None,
                }
            ],
        },
        {
            "version": 1,
            "next_id": 1,
            "todos": [
                {
                    "id": 1,
                    "title": "a",
                    "done": False,
                    "recurrence": None,
                    "due": None,
                    "priority": 1,
                }
            ],
        },
    ],
)
def test_load_rejects_invalid_documents(tmp_path, document):
    path = tmp_path / "todos.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(StorageError):
        load(path)


@pytest.mark.parametrize("priority", ["urgent", None, 1])
def test_load_rejects_invalid_priority(tmp_path, priority):
    path = tmp_path / "todos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "next_id": 2,
                "todos": [
                    {
                        "id": 1,
                        "title": "a",
                        "done": False,
                        "recurrence": None,
                        "due": None,
                        "priority": priority,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StorageError, match=r"todo 1: invalid priority"):
        load(path)


def test_load_accepts_null_recurrence_and_due(tmp_path):
    path = tmp_path / "todos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "next_id": 2,
                "todos": [{"id": 1, "title": "a", "done": False, "recurrence": None, "due": None}],
            }
        ),
        encoding="utf-8",
    )
    loaded, next_id = load(path)
    assert loaded == {1: Todo(id=1, title="a")}
    assert next_id == 2


def test_storage_error_is_exported():
    import todo_app

    assert todo_app.StorageError is StorageError
    assert "StorageError" in todo_app.__all__


def test_load_does_not_create_file(tmp_path):
    path: Path = tmp_path / "todos.json"
    load(path)
    assert list(tmp_path.iterdir()) == []


def test_document_shape_for_mixed_todos():
    todos = [
        Todo(id=1, title="milk", done=False, recurrence=None, due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", due=None, priority="high"),
        Todo(
            id=3, title="weekly review", done=False, recurrence="weekly", due=None, priority="low"
        ),
    ]
    assert document(todos, next_id=4) == {
        "version": 1,
        "next_id": 4,
        "todos": [
            {
                "id": 1,
                "title": "milk",
                "done": False,
                "recurrence": None,
                "due": "2026-01-31",
                "priority": "medium",
            },
            {
                "id": 2,
                "title": "water plants",
                "done": True,
                "recurrence": "3d",
                "due": None,
                "priority": "high",
            },
            {
                "id": 3,
                "title": "weekly review",
                "done": False,
                "recurrence": "weekly",
                "due": None,
                "priority": "low",
            },
        ],
    }


def test_document_accepts_any_iterable():
    todos = (Todo(id=1, title="a"), Todo(id=2, title="b"))
    assert [todo["id"] for todo in document(todos, next_id=3)["todos"]] == [1, 2]


def test_save_writes_exactly_the_document(tmp_path):
    path = tmp_path / "todos.json"
    todos = [
        Todo(id=1, title="milk", due=date(2026, 1, 31)),
        Todo(id=2, title="water plants", done=True, recurrence="3d", priority="high"),
    ]
    save(path, todos, next_id=3)

    assert json.loads(path.read_text(encoding="utf-8")) == document(todos, next_id=3)
