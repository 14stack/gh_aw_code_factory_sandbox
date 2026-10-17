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
