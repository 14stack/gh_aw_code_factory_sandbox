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


def test_next_id_starts_at_one():
    assert TodoStore().next_id == 1


def test_next_id_increments_after_add():
    store = TodoStore()
    store.add("a")
    assert store.next_id == 2
    store.add("b")
    assert store.next_id == 3


def test_next_id_unchanged_by_reads():
    store = TodoStore()
    store.add("a")
    store.add("b")
    store.complete(1)
    before = store.next_id

    store.list()
    store.counts()
    store.get(2)

    assert store.next_id == before


def test_next_id_is_read_only():
    store = TodoStore()
    with pytest.raises(AttributeError):
        store.next_id = 5


def test_set_due_sets_and_clears():
    store = TodoStore()
    store.add("spec")
    assert store.set_due(1, date(2026, 11, 1)).due == date(2026, 11, 1)
    assert store.set_due(1, None).due is None


def test_set_due_keeps_recurrence():
    store = TodoStore()
    store.add("water plants", recurrence="3d")
    todo = store.set_due(1, date(2026, 11, 1))
    assert todo.recurrence == "3d"
    assert store.set_due(1, None).recurrence == "3d"


def test_set_due_unknown_id_raises():
    store = TodoStore()
    with pytest.raises(TodoNotFoundError):
        store.set_due(1, date(2026, 11, 1))


def test_store_with_path_persists_set_due(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("spec")
    store.set_due(1, date(2026, 11, 1))

    reloaded = TodoStore(path)
    assert reloaded.get(1).due == date(2026, 11, 1)

    reloaded.set_due(1, None)
    assert TodoStore(path).get(1).due is None


def test_list_status_open_returns_only_open_in_sort_order():
    store = TodoStore()
    store.add("a")
    store.add("b", due=date(2026, 1, 31))
    store.add("c")
    store.complete(2)
    assert [t.id for t in store.list(status="open")] == [1, 3]


def test_list_status_done_returns_only_done():
    store = TodoStore()
    store.add("a")
    store.add("b")
    store.add("c")
    store.complete(3)
    store.complete(1)
    assert [t.id for t in store.list(status="done")] == [1, 3]


def test_list_status_overdue_returns_open_past_due_only():
    today = date.today()
    store = TodoStore()
    store.add("past", due=date(2000, 1, 1))
    store.add("future", due=date(2999, 1, 1))
    store.add("undated")
    store.add("today", due=today)
    assert [t.id for t in store.list(status="overdue")] == [1]


def test_list_status_overdue_excludes_done_todo_with_past_due():
    store = TodoStore()
    store.add("past", due=date(2000, 1, 1))
    store.add("also past", due=date(2000, 1, 2))
    store.complete(1)
    assert [t.id for t in store.list(status="overdue")] == [2]


def test_list_invalid_status_raises_value_error():
    store = TodoStore()
    store.add("a")
    with pytest.raises(ValueError):
        store.list(status="bogus")


def test_list_status_combines_with_priority():
    store = TodoStore()
    store.add("high open", priority="high")
    store.add("high done", priority="high")
    store.add("low open", priority="low")
    store.complete(2)
    assert [t.id for t in store.list(status="open", priority="high")] == [1]
    assert [t.id for t in store.list(status="done", priority="high")] == [2]
    assert [t.id for t in store.list(status="done", priority="low")] == []


def test_reopen_done_todo():
    store = TodoStore()
    store.add("a")
    store.complete(1)
    reopened = store.reopen(1)
    assert reopened.id == 1
    assert reopened.done is False
    assert store.get(1).done is False


def test_reopen_open_todo_stays_open():
    store = TodoStore()
    store.add("a")
    assert store.reopen(1).done is False
    assert store.get(1).done is False


def test_reopen_unknown_id_raises():
    store = TodoStore()
    with pytest.raises(TodoNotFoundError):
        store.reopen(1)


def test_store_with_path_persists_reopen(tmp_path):
    path = tmp_path / "todos.json"
    store = TodoStore(path)
    store.add("a")
    store.complete(1)
    store.reopen(1)

    assert TodoStore(path).get(1).done is False


def test_add_stores_tags():
    store = TodoStore()
    assert store.add("milk", tags=["home"]).tags == ("home",)
    assert store.add("plain").tags == ()


def test_add_dedupes_and_sorts_tags():
    store = TodoStore()
    todo = store.add("milk", tags=["work", "home", "work"])
    assert todo.tags == ("home", "work")


def test_add_rejects_invalid_tag():
    store = TodoStore()
    with pytest.raises(ValueError):
        store.add("milk", tags=["Work"])
    with pytest.raises(ValueError):
        store.add("milk", tags=["no spaces"])
    assert store.list() == []
    assert store.add("milk").id == 1


def test_list_filters_by_tag():
    store = TodoStore()
    work = store.add("work", tags=["work"])
    home = store.add("home", tags=["home"])
    both = store.add("both", tags=["work", "home"])
    store.add("none")
    assert [t.id for t in store.list(tags=["work"])] == [work.id, both.id]
    assert [t.id for t in store.list(tags=["home"])] == [home.id, both.id]


def test_list_requires_every_tag():
    store = TodoStore()
    store.add("work", tags=["work"])
    both = store.add("both", tags=["work", "home"])
    assert [t.id for t in store.list(tags=["work", "home"])] == [both.id]
    assert store.list(tags=["work", "missing"]) == []


def test_list_tag_combines_with_status_and_priority():
    store = TodoStore()
    high_open = store.add("high open", priority="high", tags=["work"])
    high_done = store.add("high done", priority="high", tags=["work"])
    low_open = store.add("low open", priority="low", tags=["work"])
    store.complete(high_done.id)
    assert [t.id for t in store.list(tags=["work"], status="open", priority="high")] == [
        high_open.id
    ]
    assert [t.id for t in store.list(tags=["work"], status="done")] == [high_done.id]
    assert [t.id for t in store.list(tags=["work"], priority="low")] == [low_open.id]


def test_list_rejects_invalid_tag():
    store = TodoStore()
    store.add("milk", tags=["home"])
    with pytest.raises(ValueError):
        store.list(tags=["Home"])


def test_complete_recurring_spawn_inherits_tags():
    store = TodoStore()
    store.add("water plants", recurrence="3d", tags=["home", "garden"])
    store.complete(1)
    assert store.get(2).tags == ("garden", "home")


def test_retag_replaces_tag_across_todos():
    store = TodoStore()
    store.add("milk", tags=["home", "shoping"])
    store.add("bread", tags=["shoping"])
    store.add("report", tags=["work"])
    assert store.retag("shoping", "shopping") == 2
    assert store.get(1).tags == ("home", "shopping")
    assert store.get(2).tags == ("shopping",)
    assert store.get(3).tags == ("work",)


def test_retag_includes_done_todos():
    store = TodoStore()
    store.add("milk", tags=["shoping"])
    store.complete(1)
    assert store.retag("shoping", "shopping") == 1
    assert store.get(1).done is True
    assert store.get(1).tags == ("shopping",)


def test_retag_dedupes_when_new_tag_already_present():
    store = TodoStore()
    store.add("milk", tags=["home", "shoping", "shopping"])
    assert store.retag("shoping", "shopping") == 1
    assert store.get(1).tags == ("home", "shopping")


def test_retag_keeps_tags_sorted():
    store = TodoStore()
    store.add("milk", tags=["work", "aaa"])
    assert store.retag("work", "zzz") == 1
    assert store.get(1).tags == ("aaa", "zzz")


def test_retag_without_match_returns_zero():
    store = TodoStore()
    store.add("milk", tags=["home"])
    assert store.retag("work", "office") == 0
    assert store.get(1).tags == ("home",)


def test_retag_same_word_returns_zero_and_keeps_tags():
    store = TodoStore()
    store.add("milk", tags=["home", "work"])
    assert store.retag("home", "home") == 0
    assert store.get(1).tags == ("home", "work")


def test_retag_rejects_invalid_old_tag():
    store = TodoStore()
    store.add("milk", tags=["home"])
    with pytest.raises(ValueError):
        store.retag("Home", "work")
    assert store.get(1).tags == ("home",)


def test_retag_rejects_invalid_new_tag():
    store = TodoStore()
    store.add("milk", tags=["home"])
    with pytest.raises(ValueError):
        store.retag("home", "no spaces")
    assert store.get(1).tags == ("home",)
