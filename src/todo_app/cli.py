"""Command-line interface that runs a sequence of todo commands against one store.

Example:
    todo add "buy milk" add "write spec" done 1 list count
"""

import sys
from datetime import date, timedelta

from todo_app import export
from todo_app.storage import StorageError, default_path
from todo_app.store import (
    DEFAULT_PRIORITY,
    PRIORITIES,
    STATUSES,
    Todo,
    TodoNotFoundError,
    TodoStore,
    normalize_tags,
)

_COMMANDS = frozenset(
    {
        "add",
        "done",
        "undo",
        "rm",
        "list",
        "find",
        "show",
        "clear",
        "count",
        "prio",
        "due",
        "retag",
        "export",
    }
)


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


def _parse_when(token: str) -> date | None:
    """Return the due date for ``token``, or None if it is not a valid due date."""
    if token == "none":
        return None
    if token.startswith("+") and token.endswith("d"):
        try:
            days = int(token[1:-1])
        except ValueError:
            return None
        if days >= 1:
            return date.today() + timedelta(days=days)
        return None
    return _parse_due(token)


def _format_todo(todo: Todo) -> str:
    """Render ``todo`` in the same format as a ``list`` line."""
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
    if todo.tags:
        line += " " + " ".join(f"#{tag}" for tag in sorted(todo.tags))
    return line


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
            tags: list[str] = []
            i += 2
            error: str | None = None
            while i < len(args) and args[i] in ("every", "due", "priority", "tag"):
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
                    token = args[i + 1] if i + 1 < len(args) else ""
                    i += 2 if i + 1 < len(args) else 1
                    priority = _parse_priority(token)
                    if priority is None:
                        error = f"error: invalid priority {token!r}"
                        break
                elif keyword == "tag":
                    # A following command keyword is not a tag word, so it stays a command.
                    has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
                    token = args[i + 1] if has_token else ""
                    i += 2 if has_token else 1
                    if not has_token:
                        error = "error: missing tag"
                        break
                    try:
                        tags.extend(normalize_tags([token]))
                    except ValueError:
                        error = f"error: invalid tag {token!r}"
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
                title,
                recurrence=recurrence,
                due=due,
                priority=priority or DEFAULT_PRIORITY,
                tags=tags,
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
        elif cmd == "undo":
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
                store.reopen(todo_id)
                out.append(f"reopened {todo_id}")
            except TodoNotFoundError:
                out.append(f"error: no todo {todo_id}")
            i += 2
        elif cmd == "show":
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
                out.append(_format_todo(store.get(todo_id)))
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
        elif cmd == "due":
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
            when = args[i + 2] if i + 2 < len(args) else ""
            i += 3
            due = _parse_when(when)
            if when != "none" and due is None:
                out.append(f"error: invalid due date {when!r}")
                continue
            try:
                todo = store.set_due(todo_id, due)
                out.append(_format_todo(todo))
            except TodoNotFoundError:
                out.append(f"error: no todo {todo_id}")
        elif cmd == "list":
            # ``done`` directly after ``list`` is a status filter, not the command.
            status: str | None = None
            priority: str | None = None
            tags: list[str] = []
            errors: list[str] = []
            i += 1
            while i < len(args) and (args[i] not in _COMMANDS or args[i] == "done"):
                token = args[i]
                i += 1
                if token == "tag":
                    # ``tag`` consumes the next token unconditionally as the tag word.
                    if i >= len(args):
                        errors.append("error: missing tag")
                        break
                    word = args[i]
                    i += 1
                    try:
                        tags.extend(normalize_tags([word]))
                    except ValueError:
                        errors.append(f"error: invalid tag {word!r}")
                elif token in STATUSES and status is None:
                    status = token
                elif _parse_priority(token) is not None and priority is None:
                    priority = token
                else:
                    errors.append(f"error: invalid filter {token!r}")
            if errors:
                out.extend(errors)
                continue
            for todo in store.list(priority=priority, status=status, tags=tags):
                out.append(_format_todo(todo))
        elif cmd == "retag":
            # Following command keywords are not tag words, so they stay commands.
            words: list[str] = []
            error = None
            i += 1
            for _ in range(2):
                has_token = i < len(args) and args[i] not in _COMMANDS
                if not has_token:
                    error = "error: missing tag"
                    break
                words.append(args[i])
                i += 1
            if error is not None:
                out.append(error)
                continue
            old, new = words
            invalid = None
            for word in (old, new):
                try:
                    normalize_tags((word,))
                except ValueError:
                    invalid = word
                    break
            if invalid is not None:
                out.append(f"error: invalid tag {invalid!r}")
                continue
            count = store.retag(old, new)
            out.append(f"retagged {count} todo(s)")
        elif cmd == "find":
            # A following command keyword is not the search text, so it stays a command.
            has_token = i + 1 < len(args) and args[i + 1] not in _COMMANDS
            if not has_token:
                out.append("error: missing text")
                i += 1
                continue
            text = args[i + 1].lower()
            i += 2
            for todo in store.list():
                if text in todo.title.lower():
                    out.append(_format_todo(todo))
        elif cmd == "export":
            fmt = export.DEFAULT_FORMAT
            i += 1
            if i < len(args) and args[i] not in _COMMANDS:
                token = args[i]
                i += 1
                if token not in export.FORMATS:
                    out.append(f"error: invalid format {token!r}")
                    continue
                fmt = token
            out.extend(export.render(store.list(), fmt, next_id=store.next_id))
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
