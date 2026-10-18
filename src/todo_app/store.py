"""In-memory todo store."""

from dataclasses import dataclass
from datetime import date


class TodoNotFoundError(KeyError):
    """Raised when a todo id does not exist."""


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    recurrence: str | None = None
    due: date | None = None


class TodoStore:
    """Keeps todos in memory, keyed by an auto-incrementing id."""

    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id = 1

    def add(self, title: str, recurrence: str | None = None, due: date | None = None) -> Todo:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        todo = Todo(id=self._next_id, title=title, recurrence=recurrence, due=due)
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
            self.add(todo.title, recurrence=todo.recurrence)
        return todo

    def remove(self, todo_id: int) -> None:
        self.get(todo_id)
        del self._todos[todo_id]

    def clear_done(self) -> int:
        done_ids = [todo_id for todo_id, todo in self._todos.items() if todo.done]
        for todo_id in done_ids:
            del self._todos[todo_id]
        return len(done_ids)

    def counts(self) -> tuple[int, int]:
        """Return the number of open and done todos as ``(open, done)``."""
        open_count = sum(1 for todo in self._todos.values() if not todo.done)
        done_count = sum(1 for todo in self._todos.values() if todo.done)
        return open_count, done_count

    def list(self, *, include_done: bool = True) -> list[Todo]:
        todos = sorted(self._todos.values(), key=lambda t: (t.due is None, t.due or date.min, t.id))
        if include_done:
            return todos
        return [t for t in todos if not t.done]
