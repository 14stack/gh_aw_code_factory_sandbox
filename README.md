# gh_aw_code_factory_sandbox

Sandbox product repo for [gh_aw_code_factory](https://github.com/14stack/gh_aw_code_factory): a tiny Python todo
service that the factory's AI agents refine, implement, review and fix stories against.

```bash
pip install -e ".[dev]"
pytest
todo add "buy milk" add "write spec" done 1 list
```

## Where todos are stored

Todos are saved to `~/.todo/todos.json` by default, so one global list is shared by every `todo` invocation. The
`~/.todo` directory is created on the first write; a read-only command such as `todo list` on a fresh machine leaves
no files behind.

Set `TODO_FILE` to use another file. A relative value resolves against the current directory:

```bash
TODO_FILE=/path/to/todos.json todo list
```

The file is versioned JSON (`{"version": 1, "next_id": ..., "todos": [...]}`), where `due` is an ISO date or `null`,
`recurrence` is a string or `null` and `priority` is one of `high`, `medium` or `low`. A file written before the
`priority` field existed still loads, with every todo at `medium` priority, and is rewritten with an explicit
`priority` on the next save. A missing file is not an error: the first run starts with an empty list. An unreadable
or corrupt file prints `error: cannot read <path>: <reason>` and exits non-zero without overwriting it.

See [AGENTS.md](AGENTS.md) for the commands and conventions the agents follow.

## Finding todos

`todo find <text>` prints every todo, open and done, whose title contains `<text>` case-insensitively, in the same
format and order as `list`. No match prints nothing. The search is a plain substring match: no regex, no fuzzy
matching.

```bash
todo find milk
```

## Exporting todos

`todo export [md|csv|json]` prints every todo, open and done, in `list` order. Nothing is written to disk, so
redirect the output wherever you want it. The format defaults to `md`:

- `md` prints one `- [ ] <id>: <title>` line per open todo and `- [x] <id>: <title>` per done todo, with the same
  `(every Nd)` / `(weekly)` and `(due YYYY-MM-DD)` suffixes as `list`, but no priority markers and no `OVERDUE`.
- `csv` prints the header `id,title,done,recurrence,due,priority` then one row per todo; `done` is `true` or
  `false`, and `recurrence` and `due` are empty when unset.
- `json` prints the versioned storage document on one line, in the same shape as the todo file, so it can be used
  as a backup.

An unknown format prints `error: invalid format '<token>'` and the rest of the command chain still runs.

```bash
todo export csv > todos.csv
todo export json > todos.json
```

