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
