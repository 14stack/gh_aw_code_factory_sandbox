"""Render todos as Markdown, CSV or JSON for the ``export`` command."""

import csv
import io
import json
from collections.abc import Iterable

from todo_app import storage
from todo_app.store import Todo

FORMATS: tuple[str, ...] = ("md", "csv", "json")
DEFAULT_FORMAT = "md"

_CSV_HEADER = ("id", "title", "done", "recurrence", "due", "priority")


def render(todos: Iterable[Todo], fmt: str = DEFAULT_FORMAT, *, next_id: int = 1) -> list[str]:
    """Return the output lines for ``todos`` in ``fmt``."""
    if fmt == "md":
        return [_markdown_line(todo) for todo in todos]
    if fmt == "csv":
        return _csv_lines(todos)
    if fmt == "json":
        return [json.dumps(storage.document(todos, next_id))]
    raise ValueError(f"invalid format {fmt!r}")


def _markdown_line(todo: Todo) -> str:
    mark = "x" if todo.done else " "
    line = f"- [{mark}] {todo.id}: {todo.title}"
    if todo.recurrence is not None:
        if todo.recurrence == "weekly":
            line += " (weekly)"
        else:
            line += f" (every {todo.recurrence})"
    if todo.due is not None:
        line += f" (due {todo.due.isoformat()})"
    return line


def _csv_lines(todos: Iterable[Todo]) -> list[str]:
    lines = [_csv_line(_CSV_HEADER)]
    for todo in todos:
        lines.append(
            _csv_line(
                (
                    str(todo.id),
                    todo.title,
                    "true" if todo.done else "false",
                    todo.recurrence or "",
                    todo.due.isoformat() if todo.due is not None else "",
                    todo.priority,
                )
            )
        )
    return lines


def _csv_line(row: Iterable[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(row)
    return buffer.getvalue().removesuffix("\n")
