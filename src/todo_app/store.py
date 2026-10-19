"""Todo store, in memory or persisted to a JSON file."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from todo_app import storage

PRIORITIES: tuple[str, ...] = ("high", "medium", "low")
STATUSES: tuple[str, ...] = ("open", "done", "overdue")
DEFAULT_PRIORITY: str = "medium"
TAG_PATTERN = re.compile(r"^[a-z0-9-]+$")


def normalize_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Return ``tags`` validated, deduplicated and sorted."""
    normalized = set()
    for tag in tags:
        if not TAG_PATTERN.fullmatch(tag):
            raise ValueError(f"invalid tag {tag!r}")
        normalized.add(tag)
    return tuple(sorted(normalized))


class TodoNotFoundError(KeyError):
    """Raised when a todo id does not exist."""


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    recurrence: str | None = None
    due: date | None = None
    priority: str = DEFAULT_PRIORITY
    tags: tuple[str, ...] = ()


class TodoStore:
    """Keeps todos keyed by an auto-incrementing id.

    With a ``path`` the store loads from that file and saves after every mutation;
    without one it stays purely in memory.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        if path is None:
            self._todos: dict[int, Todo] = {}
            self._next_id = 1
        else:
            self._todos, self._next_id = storage.load(path)

    @property
    def next_id(self) -> int:
        """Return the id the next ``add`` will use."""
        return self._next_id

    def _save(self) -> None:
        if self._path is None:
            return
        storage.save(self._path, self._todos.values(), self._next_id)

    def add(
        self,
        title: str,
        recurrence: str | None = None,
        due: date | None = None,
        priority: str = DEFAULT_PRIORITY,
        tags: Iterable[str] = (),
    ) -> Todo:
        if priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        normalized_tags = normalize_tags(tags)
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        todo = Todo(
            id=self._next_id,
            title=title,
            recurrence=recurrence,
            due=due,
            priority=priority,
            tags=normalized_tags,
        )
        self._todos[todo.id] = todo
        self._next_id += 1
        self._save()
        return todo

    def get(self, todo_id: int) -> Todo:
        try:
            return self._todos[todo_id]
        except KeyError:
            raise TodoNotFoundError(todo_id) from None

    def complete(self, todo_id: int) -> Todo:
        todo = self.get(todo_id)
        todo.done = True
        if todo.recurrence is not None:
            self.add(
                todo.title,
                recurrence=todo.recurrence,
                priority=todo.priority,
                tags=todo.tags,
            )
        self._save()
        return todo

    def reopen(self, todo_id: int) -> Todo:
        todo = self.get(todo_id)
        todo.done = False
        self._save()
        return todo

    def set_priority(self, todo_id: int, priority: str) -> Todo:
        if priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        todo = self.get(todo_id)
        todo.priority = priority
        self._save()
        return todo

    def set_due(self, todo_id: int, due: date | None) -> Todo:
        todo = self.get(todo_id)
        todo.due = due
        self._save()
        return todo

    def remove(self, todo_id: int) -> None:
        self.get(todo_id)
        del self._todos[todo_id]
        self._save()

    def clear_done(self) -> int:
        done_ids = [todo_id for todo_id, todo in self._todos.items() if todo.done]
        for todo_id in done_ids:
            del self._todos[todo_id]
        self._save()
        return len(done_ids)

    def counts(self) -> tuple[int, int]:
        """Return the number of open and done todos as ``(open, done)``."""
        open_count = sum(1 for todo in self._todos.values() if not todo.done)
        done_count = sum(1 for todo in self._todos.values() if todo.done)
        return open_count, done_count

    def tag_counts(self) -> list[tuple[str, int, int]]:
        """Return ``(tag, open, done)`` counts for every tag in use, sorted by tag."""
        counts: dict[str, list[int]] = {}
        for todo in self._todos.values():
            for tag in todo.tags:
                counts.setdefault(tag, [0, 0])[1 if todo.done else 0] += 1
        return [
            (tag, open_count, done_count)
            for tag, (open_count, done_count) in sorted(counts.items())
        ]

    def list(
        self,
        *,
        include_done: bool = True,
        priority: str | None = None,
        status: str | None = None,
        tags: Iterable[str] = (),
    ) -> list[Todo]:
        if priority is not None and priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        if status is not None and status not in STATUSES:
            raise ValueError(f"invalid status {status!r}")
        required_tags = normalize_tags(tags)
        todos = sorted(
            self._todos.values(),
            key=lambda t: (PRIORITIES.index(t.priority), t.due is None, t.due or date.min, t.id),
        )
        if priority is not None:
            todos = [t for t in todos if t.priority == priority]
        if required_tags:
            todos = [t for t in todos if all(tag in t.tags for tag in required_tags)]
        if status == "open":
            todos = [t for t in todos if not t.done]
        elif status == "done":
            todos = [t for t in todos if t.done]
        elif status == "overdue":
            today = date.today()
            todos = [t for t in todos if not t.done and t.due is not None and t.due < today]
        if include_done:
            return todos
        return [t for t in todos if not t.done]
