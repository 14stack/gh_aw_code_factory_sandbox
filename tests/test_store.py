from datetime import date

import pytest

from todo_app import TodoNotFoundError, TodoStore


def test_add_assigns_incrementing_ids():
    store = TodoStore()
    assert store.add("a").id == 1
    assert store.add("b").id == 2


def test_add_strips_and_rejects_empty_titles():
    store = TodoStore()
    assert store.add("  milk ").title == "milk"
    with pytest.raises(ValueError):
        store.add("   ")


def test_add_stores_recurrence():
    store = TodoStore()
    assert store.add("water plants", recurrence="3d").recurrence == "3d"
    assert store.add("plain").recurrence is None


def test_complete_recurring_spawns_fresh_todo():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    completed = store.complete(1)
    assert completed.id == 1
    assert completed.done is True
    spawned = store.get(2)
    assert spawned.title == "water plants"
    assert spawned.recurrence == "3d"
    assert spawned.done is False
    assert [t.id for t in store.list()] == [1, 2]


def test_completing_spawn_spawns_again():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    store.complete(1)
    store.complete(2)
    spawned = store.get(3)
    assert spawned.title == "water plants"
    assert spawned.recurrence == "3d"
    assert spawned.done is False


def test_add_stores_due_date():
    store = TodoStore()
    assert store.add("spec", due=date(2026, 1, 31)).due == date(2026, 1, 31)
    assert store.add("plain").due is None


def test_list_sorts_dated_first_ascending_undated_last():
    store = TodoStore()
    undated = store.add("undated")
    later = store.add("later", due=date(2026, 3, 1))
    sooner = store.add("sooner", due=date(2026, 1, 31))
    assert [t.id for t in store.list()] == [sooner.id, later.id, undated.id]


def test_list_keeps_id_order_for_equal_due_dates():
    store = TodoStore()
    first = store.add("first", due=date(2026, 1, 31))
    second = store.add("second", due=date(2026, 1, 31))
    assert [t.id for t in store.list()] == [first.id, second.id]


def test_complete_and_filter():
    store = TodoStore()
    store.add("a")
    store.add("b")
    store.complete(1)
    assert [t.id for t in store.list()] == [1, 2]
    assert [t.id for t in store.list(include_done=False)] == [2]


def test_remove_and_missing_ids():
    store = TodoStore()
    store.add("a")
    store.remove(1)
    assert store.list() == []
    with pytest.raises(TodoNotFoundError):
        store.get(1)
    with pytest.raises(TodoNotFoundError):
        store.complete(42)


def test_clear_done_removes_only_done_and_returns_count():
    store = TodoStore()
    store.add("a")
    store.add("b")
    store.add("c")
    store.complete(1)
    store.complete(3)
    assert store.clear_done() == 2
    assert [t.id for t in store.list()] == [2]
    assert store.get(2).title == "b"


def test_clear_done_returns_zero_on_empty_or_all_open():
    store = TodoStore()
    assert store.clear_done() == 0
    store.add("a")
    store.add("b")
    assert store.clear_done() == 0
    assert [t.id for t in store.list()] == [1, 2]


def test_ids_not_reused_after_clear():
    store = TodoStore()
    store.add("a")
    store.complete(1)
    assert store.clear_done() == 1
    assert store.add("b").id == 2


def test_clear_done_removes_done_recurring_without_spawning():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    store.complete(1)
    assert [t.id for t in store.list()] == [1, 2]
    assert store.clear_done() == 1
    assert [t.id for t in store.list()] == [2]
    assert store.get(2).done is False


def test_counts_on_empty_store():
    assert TodoStore().counts() == (0, 0)


def test_counts_open_only():
    store = TodoStore()
    store.add("a")
    store.add("b")
    assert store.counts() == (2, 0)


def test_counts_open_and_done():
    store = TodoStore()
    store.add("a")
    store.add("b")
    store.add("c")
    store.complete(2)
    assert store.counts() == (2, 1)


def test_counts_after_complete_spawns_recurrence():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    store.complete(1)
    assert store.counts() == (1, 1)


def test_store_with_path_persists_add(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("milk", due=date(2026, 1, 31))
    store.add("water plants", recurrence="3d")

    reloaded = TodoStore(path)
    assert [t.id for t in reloaded.list()] == [1, 2]
    assert reloaded.get(1).title == "milk"
    assert reloaded.get(1).due == date(2026, 1, 31)
    assert reloaded.get(1).done is False
    assert reloaded.get(1).recurrence is None
    assert reloaded.get(2).recurrence == "3d"
    assert reloaded.get(2).due is None


def test_store_with_path_persists_complete_and_spawn(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("water plants", recurrence="3d")
    store.complete(1)

    reloaded = TodoStore(path)
    assert [(t.id, t.done) for t in reloaded.list()] == [(1, True), (2, False)]
    assert reloaded.get(2).title == "water plants"
    assert reloaded.get(2).recurrence == "3d"


def test_store_with_path_persists_priority(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("pay rent", priority="high")
    store.add("water plants", recurrence="3d", priority="low")

    reloaded = TodoStore(path)
    assert reloaded.get(1).priority == "high"
    assert reloaded.get(2).priority == "low"

    reloaded.complete(2)
    assert TodoStore(path).get(3).priority == "low"


def test_store_with_path_persists_remove_and_next_id(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("a")
    store.remove(1)

    reloaded = TodoStore(path)
    assert reloaded.list() == []
    assert reloaded.add("b").id == 2


def test_store_with_path_persists_clear_done(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("a")
    store.add("b")
    store.complete(1)
    assert store.clear_done() == 1

    reloaded = TodoStore(path)
    assert [t.id for t in reloaded.list()] == [2]
    assert reloaded.counts() == (1, 0)


def test_store_with_path_counts_persisted_todos(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("a")
    store.add("b")
    store.complete(1)

    assert TodoStore(path).counts() == (1, 1)


def test_store_with_path_to_missing_file_starts_empty(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    assert store.list() == []
    assert store.counts() == (0, 0)
    assert not path.exists()

    store.add("a")
    assert path.exists()


def test_store_without_path_stays_in_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = TodoStore()
    store.add("a")
    store.complete(1)
    store.remove(1)
    store.clear_done()

    assert TodoStore().list() == []
    assert list(tmp_path.iterdir()) == []


def test_store_with_path_reads_do_not_write(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("a")
    before = path.read_bytes()

    store.get(1)
    store.list()
    store.counts()

    assert path.read_bytes() == before


def test_add_defaults_to_medium_priority():
    store = TodoStore()
    assert store.add("milk").priority == "medium"


def test_add_stores_priority():
    store = TodoStore()
    assert store.add("pay rent", priority="high").priority == "high"
    assert store.add("tidy desk", priority="low").priority == "low"


def test_add_rejects_invalid_priority():
    store = TodoStore()
    with pytest.raises(ValueError):
        store.add("pay rent", priority="urgent")
    assert store.list() == []
    assert store.add("milk").id == 1


def test_complete_recurring_spawn_inherits_priority():
    store = TodoStore()
    store.add("water plants", recurrence="3d", priority="high")
    store.complete(1)
    assert store.get(2).priority == "high"


def test_set_priority_changes_and_returns_todo():
    store = TodoStore()
    todo = store.add("pay rent")
    returned = store.set_priority(todo.id, "high")
    assert returned is todo
    assert returned.priority == "high"
    assert store.get(todo.id).priority == "high"


def test_set_priority_rejects_invalid_level():
    store = TodoStore()
    todo = store.add("pay rent", priority="low")
    with pytest.raises(ValueError):
        store.set_priority(todo.id, "urgent")
    assert store.get(todo.id).priority == "low"


def test_set_priority_missing_id_raises():
    store = TodoStore()
    with pytest.raises(TodoNotFoundError):
        store.set_priority(7, "high")


def test_list_orders_by_priority_then_due_then_id():
    store = TodoStore()
    low = store.add("low", priority="low")
    medium = store.add("medium", due=date(2026, 1, 31))
    high_undated = store.add("high undated", priority="high")
    high_dated = store.add("high dated", due=date(2026, 2, 1), priority="high")
    assert [t.id for t in store.list()] == [
        high_dated.id,
        high_undated.id,
        medium.id,
        low.id,
    ]


def test_list_filters_by_priority():
    store = TodoStore()
    low = store.add("low", priority="low")
    high_undated = store.add("high undated", priority="high")
    high_dated = store.add("high dated", due=date(2026, 1, 31), priority="high")
    assert [t.id for t in store.list(priority="high")] == [high_dated.id, high_undated.id]
    assert [t.id for t in store.list(priority="low")] == [low.id]
    assert store.list(priority="medium") == []
    with pytest.raises(ValueError):
        store.list(priority="urgent")


def test_set_title_strips_and_returns_todo():
    store = TodoStore()
    todo = store.add("pay rent")
    returned = store.set_title(todo.id, "  pay the rent ")
    assert returned is todo
    assert returned.title == "pay the rent"
    assert store.get(todo.id).title == "pay the rent"


def test_set_title_rejects_blank_title():
    store = TodoStore()
    todo = store.add("pay rent")
    with pytest.raises(ValueError, match="title must not be empty"):
        store.set_title(todo.id, "   ")
    assert store.get(todo.id).title == "pay rent"


def test_set_title_blank_title_on_unknown_id_raises_value_error():
    store = TodoStore()
    with pytest.raises(ValueError, match="title must not be empty"):
        store.set_title(7, "  ")


def test_set_title_missing_id_raises():
    store = TodoStore()
    with pytest.raises(TodoNotFoundError):
        store.set_title(7, "pay rent")


def test_set_title_keeps_other_fields():
    store = TodoStore()
    todo = store.add("water plants", recurrence="3d", due=date(2026, 1, 31), priority="high")
    store.complete(todo.id)
    store.set_title(todo.id, "water the plants")
    changed = store.get(todo.id)
    assert changed.id == todo.id
    assert changed.done is True
    assert changed.priority == "high"
    assert changed.due == date(2026, 1, 31)
    assert changed.recurrence == "3d"


def test_store_with_path_persists_title(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("pay rent")
    store.set_title(1, "pay the rent")

    reloaded = TodoStore(path)
    assert reloaded.get(1).title == "pay the rent"


def test_complete_recurring_spawn_uses_new_title():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    store.set_title(1, "water the plants")
    store.complete(1)
    assert store.get(2).title == "water the plants"
