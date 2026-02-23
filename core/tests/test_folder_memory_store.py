from __future__ import annotations

import json
from datetime import datetime

import pytest

from k.agent.memory.entities import MemoryRecord
from k.agent.memory.folder import FolderMemoryStore


def test_folder_store_get_latest_and_get_by_id(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    r1 = MemoryRecord(
        in_channel="test",
        input="i1",
        compacted=["c1"],
        output="o1",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    store.append(r1)

    r1_path = root / "records" / "2026" / "01" / "01" / "00" / f"{r1.id_}.core.json"
    assert r1_path.exists()
    assert (root / "order.jsonl").exists()
    core_payload = json.loads(r1_path.read_text(encoding="utf-8"))
    assert core_payload["in_channel"] == "test"
    assert core_payload["out_channel"] is None
    assert core_payload["compacted"] == ["c1"]
    assert "input" not in core_payload
    assert "output" not in core_payload
    assert "detailed" not in core_payload

    r1_detailed_path = (
        root / "records" / "2026" / "01" / "01" / "00" / f"{r1.id_}.detailed.jsonl"
    )
    assert r1_detailed_path.exists()
    detailed_lines = r1_detailed_path.read_text(encoding="utf-8").splitlines()
    assert json.loads(detailed_lines[0]) == "i1"
    assert json.loads(detailed_lines[1]) == "o1"
    assert detailed_lines[2:] == []

    assert not (
        root / "records" / "2026" / "01" / "01" / "00" / f"{r1.id_}.compacted.json"
    ).exists()

    r2 = MemoryRecord(
        in_channel="test",
        input="i2",
        compacted=["c2"],
        output="o2",
        detailed=[],
        created_at=datetime(2026, 1, 2, 0, 0, 0),
        parents=[r1.id_],
    )
    store.append(r2)

    # Force a reload from disk so assertions cover the (de)serialization path.
    store.refresh()

    assert store.get_latest() == r2.id_
    assert store.get_by_id(r1.id_) == r1
    assert store.get_by_id(str(r1.id_)) == r1
    assert store.get_by_ids({r2.id_, r1.id_}) == [r1, r2]
    with pytest.raises(ValueError, match="Invalid MemoryRecord id"):
        store.get_by_id("not-a-uuid")


def test_folder_store_get_parents_children_and_ancestors(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    parent = MemoryRecord(
        in_channel="test",
        input="i1",
        compacted=["c1"],
        output="o1",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        children=[],
    )
    store.append(parent)

    child = MemoryRecord(
        in_channel="test",
        input="i2",
        compacted=["c2"],
        output="o2",
        detailed=[],
        created_at=datetime(2026, 1, 1, 1, 0, 0),
        parents=[parent.id_],
        children=[],
    )
    store.append(child)

    assert store.get_parents(child) == [parent.id_]
    assert store.get_parents(child.id_) == [parent.id_]
    assert store.get_children(parent) == [child.id_]
    assert store.get_children(parent.id_) == [child.id_]

    missing_child_id = "zzzzzzzz"
    missing = MemoryRecord(
        in_channel="test",
        input="i3",
        compacted=["c3"],
        output="o3",
        detailed=[],
        created_at=datetime(2026, 1, 1, 2, 0, 0),
        parents=[child.id_],
        children=[missing_child_id],
    )
    store.append(missing)

    assert store.get_children(missing) == [missing_child_id]
    assert store.get_parents(missing) == [child.id_]
    assert store.get_by_id(child.id_) is not None
    assert missing.id_ in store.get_by_id(child.id_).children  # type: ignore[union-attr]

    with pytest.raises(KeyError, match="Missing child record"):
        store.get_children(missing, strict=True)

    assert store.get_ancestors(missing) == [child.id_, parent.id_]
    assert store.get_ancestors(missing, level=0) == []
    assert store.get_ancestors(missing, level=1) == [child.id_]
    assert store.get_ancestors(missing, level=2) == [child.id_, parent.id_]

    # After reload, dangling child links are dropped.
    store.refresh()
    reloaded_missing = store.get_by_id(missing.id_)
    assert reloaded_missing is not None
    assert store.get_children(reloaded_missing) == []
    assert store.get_children(reloaded_missing, strict=True) == []


def test_folder_store_append_ignores_missing_parent_ids(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    parent = MemoryRecord(
        in_channel="test",
        input="p-in",
        compacted=["p-c"],
        output="p-out",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    store.append(parent)

    missing_parent_id = MemoryRecord(
        in_channel="test",
        input="m-in",
        output="m-out",
    ).id_
    child = MemoryRecord(
        in_channel="test",
        input="c-in",
        compacted=["c-c"],
        output="c-out",
        detailed=[],
        created_at=datetime(2026, 1, 1, 1, 0, 0),
        parents=[parent.id_, missing_parent_id],
    )
    store.append(child)

    assert child.parents == [parent.id_]
    assert store.get_parents(child) == [parent.id_]
    assert store.get_children(parent) == [child.id_]


def test_folder_store_repairs_links_when_middle_record_missing(tmp_path) -> None:
    root = tmp_path / "mem"
    writer = FolderMemoryStore(root)

    grandparent = MemoryRecord(
        in_channel="test",
        input="gp-in",
        compacted=["gp-c"],
        output="gp-out",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    writer.append(grandparent)

    parent = MemoryRecord(
        in_channel="test",
        input="p-in",
        compacted=["p-c"],
        output="p-out",
        detailed=[],
        created_at=datetime(2026, 1, 1, 1, 0, 0),
        parents=[grandparent.id_],
    )
    writer.append(parent)

    child = MemoryRecord(
        in_channel="test",
        input="c-in",
        compacted=["c-c"],
        output="c-out",
        detailed=[],
        created_at=datetime(2026, 1, 1, 2, 0, 0),
        parents=[parent.id_],
    )
    writer.append(child)

    missing_core = (
        root / "records" / "2026" / "01" / "01" / "01" / f"{parent.id_}.core.json"
    )
    missing_detailed = (
        root / "records" / "2026" / "01" / "01" / "01" / f"{parent.id_}.detailed.jsonl"
    )
    missing_core.unlink()
    missing_detailed.unlink()

    repaired = FolderMemoryStore(root)
    assert repaired.get_by_id(parent.id_) is None
    assert repaired.get_children(grandparent.id_) == [child.id_]
    assert repaired.get_parents(child.id_) == [grandparent.id_]

    order_lines = (root / "order.jsonl").read_text(encoding="utf-8").splitlines()
    order_ids = [json.loads(line)["id"] for line in order_lines if line.strip()]
    assert order_ids == [grandparent.id_, child.id_]


def test_folder_store_get_between(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    r1 = MemoryRecord(
        in_channel="test",
        input="i1",
        compacted=["c1"],
        output="o1",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    r2 = MemoryRecord(
        in_channel="test",
        input="i2",
        compacted=["c2"],
        output="o2",
        detailed=[],
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    r3 = MemoryRecord(
        in_channel="test",
        input="i3",
        compacted=["c3"],
        output="o3",
        detailed=[],
        created_at=datetime(2026, 1, 2, 0, 0, 0),
    )
    store.append(r1)
    store.append(r2)
    store.append(r3)

    assert store.get_between(datetime(2026, 1, 1), datetime(2026, 1, 2)) == [
        r1.id_,
        r2.id_,
        r3.id_,
    ]
    assert store.get_between(
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
        include_end=False,
    ) == [r1.id_, r2.id_]


def test_folder_store_auto_refreshes_on_external_append(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    r1 = MemoryRecord(
        in_channel="test",
        input="i1",
        compacted=["c1"],
        output="o1",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    store.append(r1)
    assert store.get_latest() == r1.id_

    external = FolderMemoryStore(root)
    r2 = MemoryRecord(
        in_channel="test",
        input="i2",
        compacted=["c2"],
        output="o2",
        detailed=[],
        created_at=datetime(2026, 1, 2, 0, 0, 0),
    )
    external.append(r2)

    assert store.get_latest() == r2.id_


def test_folder_store_rebuild_order_ignores_detailed_files(tmp_path) -> None:
    root = tmp_path / "mem"
    store = FolderMemoryStore(root)

    r1 = MemoryRecord(
        in_channel="test",
        input="i1",
        compacted=["c1"],
        output="o1",
        detailed=[],
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    store.append(r1)

    # Simulate a missing index file; the store should rebuild the order from
    # record files without treating `*.detailed.jsonl` as a record file.
    (root / "order.jsonl").unlink()

    rebuilt = FolderMemoryStore(root)
    assert rebuilt.get_latest() == r1.id_
    assert rebuilt.get_by_id(r1.id_) == r1
