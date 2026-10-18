"""In-memory todo store."""

from dataclasses import dataclass
from datetime import date

PRIORITIES: tuple[str, ...] = ("high", "medium", "low")
DEFAULT_PRIORITY: str = "medium"


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


class TodoStore:
    """Keeps todos in memory, keyed by an auto-incrementing id."""

    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id = 1

    def add(
        self,
        title: str,
        recurrence: str | None = None,
        due: date | None = None,
        priority: str = DEFAULT_PRIORITY,
    ) -> Todo:
        if priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        todo = Todo(
            id=self._next_id, title=title, recurrence=recurrence, due=due, priority=priority
        )
        self._todos[todo.id] = todo
        self._next_id += 1
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
            self.add(todo.title, recurrence=todo.recurrence, priority=todo.priority)
        return todo

    def set_priority(self, todo_id: int, priority: str) -> Todo:
        if priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        todo = self.get(todo_id)
        todo.priority = priority
        return todo

    def remove(self, todo_id: int) -> None:
        self.get(todo_id)
        del self._todos[todo_id]

    def counts(self) -> tuple[int, int]:
        """Return the number of open and done todos as ``(open, done)``."""
        open_count = sum(1 for todo in self._todos.values() if not todo.done)
        done_count = sum(1 for todo in self._todos.values() if todo.done)
        return open_count, done_count

    def list(self, *, include_done: bool = True, priority: str | None = None) -> list[Todo]:
        if priority is not None and priority not in PRIORITIES:
            raise ValueError(f"invalid priority {priority!r}")
        todos = sorted(
            self._todos.values(),
            key=lambda t: (PRIORITIES.index(t.priority), t.due is None, t.due or date.min, t.id),
        )
        if priority is not None:
            todos = [t for t in todos if t.priority == priority]
        if include_done:
            return todos
        return [t for t in todos if not t.done]
