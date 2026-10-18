"""Versioned JSON persistence for todos, written atomically."""

import json
import os
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from todo_app.store import Todo

VERSION = 1
_TODO_FIELDS = ("id", "title", "done", "recurrence", "due")


class StorageError(Exception):
    """Raised when the todo file cannot be read or parsed."""


def default_path() -> Path:
    """Return the todo file path, honouring the ``TODO_FILE`` environment variable."""
    return Path(os.environ.get("TODO_FILE", "~/.todo/todos.json")).expanduser()


def load(path: Path) -> tuple[dict[int, Todo], int]:
    """Return the todos keyed by id and the next id to assign.

    A missing file yields ``({}, 1)``; a malformed file raises ``StorageError``.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, 1
    except (OSError, UnicodeDecodeError) as exc:
        reason = getattr(exc, "strerror", None) or exc
        raise StorageError(f"cannot read file: {reason}") from None

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StorageError(f"invalid JSON: {exc.msg}") from None

    if not isinstance(document, dict):
        raise StorageError("expected a JSON object")
    if document.get("version") != VERSION:
        raise StorageError(f"unsupported version {document.get('version')!r}")

    next_id = document.get("next_id")
    if not isinstance(next_id, int) or isinstance(next_id, bool):
        raise StorageError("next_id must be an integer")

    raw_todos = document.get("todos")
    if not isinstance(raw_todos, list):
        raise StorageError("todos must be a list")

    todos: dict[int, Todo] = {}
    for raw in raw_todos:
        todo = _parse_todo(raw)
        if todo.id in todos:
            raise StorageError(f"duplicate todo id {todo.id}")
        todos[todo.id] = todo
    return todos, next_id


def save(path: Path, todos: Iterable[Todo], next_id: int) -> None:
    """Write ``todos`` and ``next_id`` to ``path`` atomically."""
    document = {
        "version": VERSION,
        "next_id": next_id,
        "todos": [
            {
                "id": todo.id,
                "title": todo.title,
                "done": todo.done,
                "recurrence": todo.recurrence,
                "due": todo.due.isoformat() if todo.due is not None else None,
            }
            for todo in todos
        ],
    }
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise StorageError(f"cannot write file: {exc.strerror or exc}") from None


def _parse_todo(raw: object) -> Todo:
    if not isinstance(raw, dict):
        raise StorageError("each todo must be a JSON object")

    missing = [key for key in _TODO_FIELDS if key not in raw]
    if missing:
        raise StorageError(f"todo is missing {', '.join(missing)}")

    todo_id = raw.get("id")
    if not isinstance(todo_id, int) or isinstance(todo_id, bool):
        raise StorageError("todo id must be an integer")

    title = raw.get("title")
    if not isinstance(title, str):
        raise StorageError(f"todo {todo_id}: title must be a string")

    done = raw.get("done")
    if not isinstance(done, bool):
        raise StorageError(f"todo {todo_id}: done must be a boolean")

    recurrence = raw.get("recurrence")
    if recurrence is not None and not isinstance(recurrence, str):
        raise StorageError(f"todo {todo_id}: recurrence must be a string or null")

    raw_due = raw.get("due")
    if raw_due is None:
        due = None
    elif isinstance(raw_due, str):
        try:
            due = date.fromisoformat(raw_due)
        except ValueError:
            raise StorageError(f"todo {todo_id}: invalid due date {raw_due!r}") from None
    else:
        raise StorageError(f"todo {todo_id}: due must be an ISO date string or null")

    return Todo(id=todo_id, title=title, done=done, recurrence=recurrence, due=due)
