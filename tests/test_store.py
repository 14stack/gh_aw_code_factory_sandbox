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
