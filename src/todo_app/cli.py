"""Command-line interface that runs a sequence of todo commands against one store.

Example:
    todo add "buy milk" add "write spec" done 1 list count
"""

import sys
from datetime import date

from todo_app.storage import StorageError, default_path
from todo_app.store import DEFAULT_PRIORITY, PRIORITIES, TodoNotFoundError, TodoStore

_COMMANDS = frozenset({"add", "done", "rm", "list", "clear", "count", "prio", "title"})


def _parse_interval(token: str) -> str | None:
    """Return the normalized recurrence for ``token``, or None if invalid."""
    if token == "weekly":
        return "weekly"
    if token.endswith("d"):
        try:
            days = int(token[:-1])
        except ValueError:
            return None
        if days >= 1:
            return f"{days}d"
    return None


def _parse_priority(token: str) -> str | None:
    """Return ``token`` when it is a known priority, or None if invalid."""
    return token if token in PRIORITIES else None


def _parse_due(token: str) -> date | None:
    """Return the due date for ``token``, or None if it is not an ISO date."""
    try:
        return date.fromisoformat(token)
    except ValueError:
        return None


def _parse_id(token: str) -> int | None:
    """Return the todo id for ``token``, or None if it is not an integer."""
    try:
        return int(token)
    except ValueError:
        return None


def run(args: list[str], store: TodoStore | None = None) -> list[str]:
    """Execute commands from ``args`` and return the output lines."""
    store = store or TodoStore()
    out: list[str] = []
    i = 0
    while i < len(args):
        cmd = args[i]
        if cmd == "add" and i + 1 < len(args):
            title = args[i + 1]
            recurrence: str | None = None
            due: date | None = None
            priority: str | None = None
            i += 2
            error: str | None = None
            while i < len(args) and args[i] in ("every", "due", "priority"):
                keyword = args[i]
                if keyword == "every":
                    if i + 1 >= len(args):
                        break
                    token = args[i + 1]
                    i += 2
                    recurrence = _parse_interval(token)
                    if recurrence is None:
                        error = f"error: invalid interval {token!r}"
                        break
                elif keyword == "priority":
                    # A following command keyword is not a priority, so it stays a command.
                    has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
                    token = args[i + 1] if has_token else ""
                    i += 2 if has_token else 1
                    priority = _parse_priority(token)
                    if priority is None:
                        error = f"error: invalid priority {token!r}"
                        break
                else:
                    # A following command keyword is not a due date, so it stays a command.
                    has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
                    token = args[i + 1] if has_token else ""
                    i += 2 if has_token else 1
                    due = _parse_due(token)
                    if due is None:
                        error = f"error: invalid due date {token!r}"
                        break
            if error is not None:
                out.append(error)
                continue
            todo = store.add(
                title, recurrence=recurrence, due=due, priority=priority or DEFAULT_PRIORITY
            )
            out.append(f"added {todo.id}: {todo.title}")
        elif cmd in ("done", "rm"):
            # A following command keyword is not an id, so it stays a command.
            has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
            if not has_token:
                out.append("error: missing id")
                i += 1
                continue
            token = args[i + 1]
            todo_id = _parse_id(token)
            if todo_id is None:
                out.append(f"error: invalid id {token!r}")
                i += 2
                continue
            try:
                if cmd == "done":
                    store.complete(todo_id)
                    out.append(f"done {todo_id}")
                else:
                    store.remove(todo_id)
                    out.append(f"removed {todo_id}")
            except TodoNotFoundError:
                out.append(f"error: no todo {todo_id}")
            i += 2
        elif cmd == "prio":
            # A following command keyword is not an id, so it stays a command.
            has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
            if not has_token:
                out.append("error: missing id")
                i += 1
                continue
            token = args[i + 1]
            todo_id = _parse_id(token)
            if todo_id is None:
                out.append(f"error: invalid id {token!r}")
                i += 2
                if i < len(args) and args[i] not in _COMMANDS:
                    i += 1
                continue
            level = args[i + 2] if i + 2 < len(args) else ""
            i += 3
            priority = _parse_priority(level)
            if priority is None:
                out.append(f"error: invalid priority {level!r}")
                continue
            try:
                store.set_priority(todo_id, priority)
                out.append(f"prio {todo_id}: {priority}")
            except TodoNotFoundError:
                out.append(f"error: no todo {todo_id}")
        elif cmd == "title":
            # A following command keyword is not an id, so it stays a command.
            has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
            if not has_token:
                out.append("error: missing id")
                i += 1
                continue
            token = args[i + 1]
            todo_id = _parse_id(token)
            if todo_id is None:
                out.append(f"error: invalid id {token!r}")
                i += 2
                if i < len(args) and args[i] not in _COMMANDS:
                    i += 1
                continue
            # After a valid id the next token is always the title, even a command keyword.
            title = args[i + 2] if i + 2 < len(args) else ""
            i += 3
            if not title:
                out.append("error: missing title")
                continue
            try:
                todo = store.set_title(todo_id, title)
            except ValueError:
                out.append("error: title must not be empty")
                continue
            except TodoNotFoundError:
                out.append(f"error: no todo {todo_id}")
                continue
            out.append(f"title {todo_id}: {todo.title}")
        elif cmd == "list":
            priority: str | None = None
            i += 1
            if i < len(args) and args[i] not in _COMMANDS:
                token = args[i]
                i += 1
                priority = _parse_priority(token)
                if priority is None:
                    out.append(f"error: invalid priority {token!r}")
                    continue
            for todo in store.list(priority=priority):
                mark = "x" if todo.done else " "
                marker = "! " if todo.priority == "high" else "↓ " if todo.priority == "low" else ""
                line = f"{marker}[{mark}] {todo.id}: {todo.title}"
                if todo.recurrence is not None:
                    if todo.recurrence == "weekly":
                        line += " (weekly)"
                    else:
                        line += f" (every {todo.recurrence})"
                if todo.due is not None:
                    overdue = ", OVERDUE" if todo.due < date.today() else ""
                    line += f" (due {todo.due.isoformat()}{overdue})"
                out.append(line)
        elif cmd == "clear":
            out.append(f"cleared {store.clear_done()}")
            i += 1
        elif cmd == "count":
            open_count, done_count = store.counts()
            out.append(f"open {open_count}, done {done_count}")
            i += 1
        else:
            out.append(f"error: unknown command {cmd!r}")
            i += 1
    return out


def main() -> int:
    path = default_path()
    try:
        store = TodoStore(path=path)
    except StorageError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    for line in run(sys.argv[1:], store):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
