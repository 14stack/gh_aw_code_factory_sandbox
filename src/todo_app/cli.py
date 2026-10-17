"""Command-line interface that runs a sequence of todo commands against one store.

Example:
    todo add "buy milk" add "write spec" done 1 list
"""

import sys

from todo_app.store import TodoNotFoundError, TodoStore


def run(args: list[str], store: TodoStore | None = None) -> list[str]:
    """Execute commands from ``args`` and return the output lines."""
    store = store or TodoStore()
    out: list[str] = []
    i = 0
    while i < len(args):
        cmd = args[i]
        if cmd == "add" and i + 1 < len(args):
            todo = store.add(args[i + 1])
            out.append(f"added {todo.id}: {todo.title}")
            i += 2
        elif cmd in ("done", "rm") and i + 1 < len(args):
            todo_id = int(args[i + 1])
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
        elif cmd == "list":
            for todo in store.list():
                mark = "x" if todo.done else " "
                out.append(f"[{mark}] {todo.id}: {todo.title}")
            i += 1
        else:
            out.append(f"error: unknown command {cmd!r}")
            i += 1
    return out


def main() -> int:
    for line in run(sys.argv[1:]):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
