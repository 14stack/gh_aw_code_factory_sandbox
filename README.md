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
