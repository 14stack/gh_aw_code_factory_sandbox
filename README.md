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
`recurrence` is a string or `null`, `priority` is one of `high`, `medium` or `low` and `tags` is a list of tag words.
A file written before the `priority` field existed still loads, with every todo at `medium` priority, and is rewritten
with an explicit `priority` on the next save. Likewise, a file written before the `tags` field existed loads with no
tags and is rewritten with an explicit `tags` list on the next save. A missing file is not an error: the first run
starts with an empty list. An unreadable or corrupt file prints `error: cannot read <path>: <reason>` and exits
non-zero without overwriting it.

See [AGENTS.md](AGENTS.md) for the commands and conventions the agents follow.

## Finding todos

`todo find <text>` prints every todo, open and done, whose title contains `<text>` case-insensitively, in the same
format and order as `list`. No match prints nothing. The search is a plain substring match: no regex, no fuzzy
matching.

```bash
todo find milk
```

## Showing one todo

`todo show <id>` prints a single todo, open or done, in the same format as a `list` line, including the priority
marker, checkbox, id, title, recurrence and due/`OVERDUE` suffix. A missing id prints `error: missing id`, an invalid
id prints `error: invalid id '<token>'` and an unknown id prints `error: no todo <id>`; in every case the rest of the
command chain still runs.

```bash
todo show 1
```

## Filtering todos

`todo list` accepts an optional status filter, and an optional priority filter from `high`, `medium` or `low`:

- `open` prints only open todos.
- `done` prints only done todos.
- `overdue` prints only open todos whose due date is before today.

A status word and a priority word can be combined in either order, so `todo list open high` and `todo list high open`
print the same lines. Each filtered list keeps the same format and order as plain `list`. Because `done` is also a
command keyword, `list done` now means the done filter. To mark a todo done and then list, put `list` after it, as in
`todo done 1 list`.

An unknown filter word, or a second status or priority word, prints `error: invalid filter '<word>'` and consumes that
word. The rest of the command chain still runs.

```bash
todo list open high
todo list high open
todo list bogus done 1 list
```

## Tagging todos

`todo add` accepts a repeatable `tag <word>` option after the title, alongside `every`, `due` and `priority`, so one
`add` can attach several tags. A tag is a lowercase word made of letters, digits and `-`; duplicate tags on one `add`
are stored once.

```bash
todo add "buy milk" tag shopping tag errands
todo add "write spec" priority high tag work
```

An invalid tag prints `error: invalid tag '<word>'` and creates no todo, and a `tag` with no word prints
`error: missing tag`; in both cases the rest of the command chain still runs. As with `due`, a following command
keyword is not a tag word, so `todo add "buy milk" tag list` reports `error: missing tag` and then runs `list`.

`todo list tag <word>` prints only the todos carrying that tag. It combines with the status and priority filters in
any order, and repeating `tag` requires every listed tag:

```bash
todo list tag work
todo list tag work open high
todo list tag work tag urgent
```

Unlike `add`, `list` consumes the word after `tag` unconditionally, so `list tag done` filters by the tag `done`
rather than by the done status. A missing word prints `error: missing tag` and an invalid word prints
`error: invalid tag '<word>'`; the rest of the command chain still runs.

`list`, `find` and `due` lines end with the todo's tags as `#tag`, separated by spaces and in alphabetical order. A
todo without tags has no suffix.

```bash
todo add "buy milk" tag shopping tag errands list
# added 1: buy milk
# [ ] 1: buy milk #errands #shopping
```

## Renaming a tag

`todo retag <old> <new>` replaces the tag `<old>` with `<new>` on every todo, open or done, and saves the change. It
prints `retagged <n> todo(s)`, where `<n>` is the number of todos that carried `<old>`. A todo that already has
`<new>` ends with a single `<new>`, and tags stay alphabetical. When no todo carries `<old>`, or when `<old>` equals
`<new>`, it prints `retagged 0 todo(s)` and changes nothing.

```bash
todo retag work office
# retagged 2 todo(s)
todo retag work work
# retagged 0 todo(s)
```

An invalid `<old>` or `<new>` prints `error: invalid tag '<word>'` for the first invalid word and changes no todo. A
missing argument prints `error: missing tag`. A following command keyword is not a tag word, so `todo retag list`
and `todo retag work list` report `error: missing tag` and then run `list`. In every error case the rest of the
command chain still runs.

## Counting todos per tag

`todo tags` prints one line per tag in use, as `#<tag> <open> open, <done> done`, sorted alphabetically by tag name.
Open and done todos both count, and a todo with several tags counts once in each. Tags that no todo carries never
appear, so with no tagged todos the command prints nothing.

```bash
todo add "buy milk" tag shopping done 1 tags
# added 1: buy milk
# done 1
# #shopping 0 open, 1 done
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

## Changing a due date

`todo due <id> <when>` sets the due date of an existing todo. `<when>` is an ISO date (`2026-11-01`), a relative
day count (`+3d` means three days from today) or `none` to clear it. The updated todo is printed in the same format
as `list`, including recurrence and `OVERDUE` markers. An invalid id prints `error: no todo <id>` and an invalid or
missing `<when>` prints `error: invalid due date <token>`; in both cases the rest of the command chain still runs.

```bash
todo due 1 2026-11-01 due 1 +3d due 1 none
```

## Reopening a todo

`todo undo <id>` marks a todo as open again, for example one marked done by mistake. It prints `reopened <id>`,
both for a done todo and for a todo that is already open. An invalid id prints `error: invalid id '<token>'` and an
unknown id prints `error: no todo <id>`; a missing id prints `error: missing id`. In every case the rest of the
command chain still runs.

```bash
todo done 1 undo 1
```

```bash
todo export csv > todos.csv
todo export json > todos.json
```

