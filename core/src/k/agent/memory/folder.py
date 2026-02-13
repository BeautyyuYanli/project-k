"""Folder-backed storage for :class:`k.agent.memory.entities.MemoryRecord`.

This store persists one record per file under a root folder, plus an append-order
index file.

Layout (relative to `root`):
- `order.jsonl`: one JSON object per non-empty line (append order), storing the
  record id, `created_at`, and relative path.
- `records/YYYY/MM/DD/HH/<id>.core.json`: one JSON blob per record (pydantic dump,
  excluding `detailed` and `compacted`), organized by `created_at`.
- `records/YYYY/MM/DD/HH/<id>.compacted.json`: a sidecar JSON file containing
  only the record's `compacted` field (a JSON array of strings). Missing sidecars
  are treated as `compacted=[]` for backward compatibility.

Design notes / invariants:
- "Latest" means the last id in `order.jsonl` (append order), not necessarily the
  max `created_at`.
- Parsing is strict: invalid ids in `order.jsonl`, invalid JSON, or invalid
  `MemoryRecord` data raises `ValueError` with path/line context.
- `append()` updates each referenced parent's `children` list (persisting parent
  records) before persisting the new record.
- Cache invalidation is keyed off `order.jsonl` mtime/size. If record files are
  modified externally without updating `order.jsonl`, call `refresh()`.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from k.agent.memory.entities import MemoryRecord
from k.agent.memory.store import (
    MemoryRecordId,
    MemoryRecordRef,
    MemoryStore,
    coerce_record_id,
)


@dataclass(slots=True)
class _CacheKey:
    mtime_ns: int
    size: int


@dataclass(frozen=True, slots=True)
class _OrderEntry:
    id_: str
    created_at: datetime
    relpath: str


class FolderMemoryStore(MemoryStore):
    """Query and append `MemoryRecord` objects stored in a folder."""

    root: Path
    encoding: str

    _cache_key: _CacheKey | None
    _records: list[MemoryRecord]
    _by_id: dict[str, MemoryRecord]
    _record_paths: dict[str, Path]

    def __init__(self, root: str | Path, *, encoding: str = "utf-8") -> None:
        self.root = Path(root)
        self.encoding = encoding
        self._cache_key = None
        self._records = []
        self._by_id = {}
        self._record_paths = {}

    def refresh(self) -> None:
        """Force a reload from disk (even if `order.jsonl` did not change)."""

        self._cache_key = None
        self._load_if_needed()

    def get_latest(self) -> str | None:
        self._load_if_needed()
        return self._records[-1].id_ if self._records else None

    def get_by_id(self, id_: MemoryRecordId) -> MemoryRecord | None:
        self._load_if_needed()
        record_id = coerce_record_id(id_)
        return self._by_id.get(record_id)

    def get_by_ids(
        self, ids: Set[MemoryRecordId], *, strict: bool = False
    ) -> list[MemoryRecord]:
        self._load_if_needed()

        record_ids = {coerce_record_id(id_) for id_ in ids}
        missing = [id_ for id_ in record_ids if id_ not in self._by_id]
        if strict and missing:
            missing_str = ", ".join(str(i) for i in sorted(missing))
            raise KeyError(f"Missing record(s): {missing_str}")

        records = [self._by_id[id_] for id_ in record_ids if id_ in self._by_id]
        order = {record.id_: idx for idx, record in enumerate(self._records)}
        records.sort(key=lambda r: (r.created_at, order.get(r.id_, 1_000_000_000)))
        return records

    def get_parents(
        self, record: MemoryRecordRef, *, strict: bool = False
    ) -> list[str]:
        self._load_if_needed()
        rec = self._coerce_record(record)
        if strict:
            missing = [id_ for id_ in rec.parents if id_ not in self._by_id]
            if missing:
                missing_str = ", ".join(str(i) for i in missing)
                raise KeyError(f"Missing parent record(s): {missing_str}")
        return list(rec.parents)

    def get_children(
        self, record: MemoryRecordRef, *, strict: bool = False
    ) -> list[str]:
        self._load_if_needed()
        rec = self._coerce_record(record)
        if strict:
            missing = [id_ for id_ in rec.children if id_ not in self._by_id]
            if missing:
                missing_str = ", ".join(str(i) for i in missing)
                raise KeyError(f"Missing child record(s): {missing_str}")
        return list(rec.children)

    def get_ancestors(
        self,
        record: MemoryRecordRef,
        *,
        level: int | None = None,
        strict: bool = False,
    ) -> list[str]:
        if level is not None and level < 0:
            raise ValueError(f"level must be >= 0 or None; got {level}")

        self._load_if_needed()
        current = self._coerce_record(record)

        if level == 0:
            return []

        ancestors: list[str] = []
        seen: set[str] = set()

        frontier = self.get_parents(current, strict=strict)
        depth = 0
        while frontier and (level is None or depth < level):
            depth += 1
            next_frontier: list[str] = []
            for parent_id in frontier:
                if parent_id in seen:
                    continue
                seen.add(parent_id)
                ancestors.append(parent_id)

                parent_record = self._by_id.get(parent_id)
                if parent_record is None:
                    if strict:
                        raise KeyError(f"Unknown parent MemoryRecord id: {parent_id}")
                    continue
                next_frontier.extend(self.get_parents(parent_record, strict=strict))
            frontier = next_frontier

        return ancestors

    def get_between(
        self,
        start: datetime,
        end: datetime,
        *,
        include_start: bool = True,
        include_end: bool = True,
    ) -> list[str]:
        if start > end:
            raise ValueError(f"start must be <= end; got start={start!r}, end={end!r}")

        self._load_if_needed()

        indexed: list[tuple[int, str, datetime]] = []
        for idx, record in enumerate(self._records):
            if _in_datetime_range(
                record.created_at,
                start,
                end,
                include_start=include_start,
                include_end=include_end,
            ):
                indexed.append((idx, record.id_, record.created_at))

        indexed.sort(key=lambda t: (t[2], t[0]))
        return [record_id for _, record_id, _ in indexed]

    def append(self, record: MemoryRecord) -> None:
        self._load_if_needed()

        if record.id_ in self._by_id:
            raise ValueError(
                f"Duplicate MemoryRecord id encountered while appending: {record.id_}"
            )

        updated_parents: list[MemoryRecord] = []
        for parent_id in record.parents:
            parent = self._by_id.get(parent_id)
            if parent is None:
                raise KeyError(f"Unknown parent MemoryRecord id: {parent_id}")
            if record.id_ not in parent.children:
                parent.children.append(record.id_)
                updated_parents.append(parent)

        for parent in updated_parents:
            self._persist_record(parent)

        record_path = self._persist_record(record)
        self._append_order_line(record, record_path)

        self._records.append(record)
        self._by_id[record.id_] = record
        self._cache_key = self._stat_key()

    def _compacted_path_for_record_path(self, record_path: Path) -> Path:
        name = record_path.name
        if name.endswith(".core.json"):
            record_id = name[: -len(".core.json")]
        elif name.endswith(".json") and not name.endswith(".compacted.json"):
            record_id = name[: -len(".json")]
        else:
            raise ValueError(f"Unexpected record filename: {record_path}")
        return record_path.with_name(f"{record_id}.compacted.json")

    def _load_if_needed(self) -> None:
        if not self.root.exists():
            self._cache_key = None
            self._records = []
            self._by_id = {}
            self._record_paths = {}
            return

        order_path = self._order_path()
        if not order_path.exists():
            self._rebuild_order_from_records()

        key = self._stat_key()
        if key is None:
            self._cache_key = None
            self._records = []
            self._by_id = {}
            self._record_paths = {}
            return

        if self._cache_key is not None and key == self._cache_key:
            return

        order_entries = _read_order_file(self._order_path(), encoding=self.encoding)

        records: list[MemoryRecord] = []
        by_id: dict[str, MemoryRecord] = {}
        record_paths: dict[str, Path] = {}
        for entry in order_entries:
            record_path = self._resolve_record_path(entry)
            if not record_path.exists():
                # Backward compatibility for relpaths written before the
                # "<id>.core.json" convention.
                if record_path.name.endswith(".core.json"):
                    legacy = record_path.with_name(
                        record_path.name[: -len(".core.json")] + ".json"
                    )
                    if legacy.exists():
                        record_path = legacy
                elif record_path.name.endswith(
                    ".json"
                ) and not record_path.name.endswith(".compacted.json"):
                    core = record_path.with_name(
                        record_path.name[: -len(".json")] + ".core.json"
                    )
                    if core.exists():
                        record_path = core
            try:
                raw = record_path.read_text(encoding=self.encoding)
            except FileNotFoundError as e:
                raise ValueError(
                    f"Missing record file for id {entry.id_}: {record_path}"
                ) from e
            try:
                record = MemoryRecord.model_validate_json(raw)
            except ValidationError as e:
                raise ValueError(
                    f"Invalid MemoryRecord JSON at {record_path}: {e}"
                ) from e
            except ValueError as e:
                raise ValueError(f"Invalid JSON at {record_path}: {e}") from e

            if record.id_ != entry.id_:
                raise ValueError(
                    f"Record id mismatch at {record_path}: expected {entry.id_}, got {record.id_}"
                )
            if record.id_ in by_id:
                raise ValueError(
                    f"Duplicate MemoryRecord id in order file: {record.id_}"
                )

            compacted_path = self._compacted_path_for_record_path(record_path)
            if compacted_path.exists():
                try:
                    compacted_raw = compacted_path.read_text(encoding=self.encoding)
                except OSError as e:
                    raise ValueError(
                        f"Failed to read compacted sidecar for id {entry.id_}: {compacted_path}: {e}"
                    ) from e
                try:
                    decoded = json.loads(compacted_raw)
                except ValueError as e:
                    raise ValueError(f"Invalid JSON at {compacted_path}: {e}") from e
                if not isinstance(decoded, list) or any(
                    not isinstance(item, str) for item in decoded
                ):
                    raise ValueError(
                        f"Invalid compacted sidecar at {compacted_path}: expected JSON array of strings"
                    )
                record = record.model_copy(update={"compacted": decoded})

            records.append(record)
            by_id[record.id_] = record
            record_paths[record.id_] = record_path

        self._records = records
        self._by_id = by_id
        self._record_paths = record_paths
        self._cache_key = key

    def _rebuild_order_from_records(self) -> None:
        records_dir = self._records_dir()
        if not records_dir.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            self._persist_order([])
            return

        indexed: list[tuple[MemoryRecord, str]] = []
        for path in records_dir.rglob("*.json"):
            if path.name.endswith(".compacted.json"):
                continue
            if (
                path.name.endswith(".json")
                and not path.name.endswith(".core.json")
                and (path.with_name(f"{path.stem}.core.json")).exists()
            ):
                # If both legacy "<id>.json" and "<id>.core.json" exist, the core
                # file is authoritative.
                continue
            try:
                raw = path.read_text(encoding=self.encoding)
            except OSError as e:
                raise ValueError(f"Failed to read MemoryRecord at {path}: {e}") from e
            try:
                record = MemoryRecord.model_validate_json(raw)
            except ValidationError as e:
                raise ValueError(f"Invalid MemoryRecord JSON at {path}: {e}") from e
            except ValueError as e:
                raise ValueError(f"Invalid JSON at {path}: {e}") from e
            indexed.append((record, str(path.relative_to(self.root))))

        # Stable order for rebuilds: by created_at then id.
        indexed.sort(key=lambda t: (t[0].created_at, str(t[0].id_)))
        self._persist_order(
            [
                _OrderEntry(
                    id_=record.id_,
                    created_at=record.created_at,
                    relpath=relpath,
                )
                for record, relpath in indexed
            ]
        )

    def _stat_key(self) -> _CacheKey | None:
        try:
            stat = self._order_path().stat()
        except FileNotFoundError:
            return None
        return _CacheKey(mtime_ns=stat.st_mtime_ns, size=stat.st_size)

    def _order_path(self) -> Path:
        return self.root / "order.jsonl"

    def _records_dir(self) -> Path:
        return self.root / "records"

    def _record_path_for(self, record: MemoryRecord) -> Path:
        return self._record_path_for_id_and_created_at(record.id_, record.created_at)

    def _record_path_for_id_and_created_at(
        self, id_: str, created_at: datetime
    ) -> Path:
        return (
            self._records_dir()
            / f"{created_at.year:04d}"
            / f"{created_at.month:02d}"
            / f"{created_at.day:02d}"
            / f"{created_at.hour:02d}"
            / f"{id_}.core.json"
        )

    def _atomic_write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = path.parent if path.parent.exists() else None
        with tempfile.NamedTemporaryFile(
            "w",
            encoding=self.encoding,
            dir=tmp_dir,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tf:
            tmp_path = Path(tf.name)
            tf.write(text)
        tmp_path.replace(path)

    def _persist_record(self, record: MemoryRecord) -> Path:
        path = self._record_paths.get(record.id_)
        if path is None:
            path = self._record_path_for(record)

        # Omit "detailed" (verbose tool traces) and "compacted" (stored as a sidecar)
        # to keep the primary record file readable and small.
        self._atomic_write_text(
            path,
            record.model_dump_json(exclude={"detailed", "compacted"}),
        )

        compacted_path = self._compacted_path_for_record_path(path)
        self._atomic_write_text(
            compacted_path,
            json.dumps(record.compacted, ensure_ascii=False),
        )

        self._record_paths[record.id_] = path
        return path

    def _persist_order(self, entries: list[_OrderEntry]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        order_path = self._order_path()
        lines: list[str] = []
        for entry in entries:
            payload = {
                "id": str(entry.id_),
                "created_at": entry.created_at.isoformat(),
                "relpath": entry.relpath,
            }
            lines.append(json.dumps(payload))
        self._atomic_write_text(order_path, "\n".join(lines) + ("\n" if lines else ""))

    def _append_order_line(self, record: MemoryRecord, record_path: Path) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._order_path().open("a", encoding=self.encoding) as f:
            payload = {
                "id": str(record.id_),
                "created_at": record.created_at.isoformat(),
                "relpath": str(record_path.relative_to(self.root)),
            }
            f.write(json.dumps(payload) + "\n")

    def _coerce_record(self, record: MemoryRecordRef) -> MemoryRecord:
        if isinstance(record, MemoryRecord):
            return record
        record_id = coerce_record_id(record)
        rec = self._by_id.get(record_id)
        if rec is None:
            raise KeyError(f"Unknown MemoryRecord id: {record_id}")
        return rec

    def _resolve_record_path(self, entry: _OrderEntry) -> Path:
        relpath = Path(entry.relpath)
        if relpath.is_absolute() or ".." in relpath.parts:
            raise ValueError(f"Invalid relpath in order.jsonl: {entry.relpath!r}")
        return self.root / relpath


def _read_order_file(path: Path, *, encoding: str) -> list[_OrderEntry]:
    entries: list[_OrderEntry] = []
    with path.open("r", encoding=encoding) as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except ValueError as e:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {e}") from e

            if not isinstance(decoded, dict):
                raise ValueError(
                    f"Invalid order entry at {path}:{line_no}: expected object, got {decoded!r}"
                )

            raw_id = decoded.get("id")
            if not isinstance(raw_id, str):
                raise ValueError(
                    f"Invalid order entry at {path}:{line_no}: missing/invalid 'id'"
                )
            try:
                record_id = coerce_record_id(raw_id)
            except ValueError as e:
                raise ValueError(
                    f"Invalid record id at {path}:{line_no}: {raw_id!r}"
                ) from e

            raw_created_at = decoded.get("created_at")
            if not isinstance(raw_created_at, str):
                raise ValueError(
                    f"Invalid order entry at {path}:{line_no}: missing/invalid 'created_at'"
                )
            try:
                created_at = datetime.fromisoformat(raw_created_at)
            except ValueError as e:
                raise ValueError(
                    f"Invalid created_at at {path}:{line_no}: {raw_created_at!r}"
                ) from e

            relpath = decoded.get("relpath")
            if not isinstance(relpath, str):
                raise ValueError(
                    f"Invalid order entry at {path}:{line_no}: missing/invalid 'relpath'"
                )

            entries.append(
                _OrderEntry(id_=record_id, created_at=created_at, relpath=relpath)
            )
    return entries


def _in_datetime_range(
    value: datetime,
    start: datetime,
    end: datetime,
    *,
    include_start: bool,
    include_end: bool,
) -> bool:
    try:
        if include_start:
            left_ok = value >= start
        else:
            left_ok = value > start
        if include_end:
            right_ok = value <= end
        else:
            right_ok = value < end
        return left_ok and right_ok
    except TypeError as e:
        raise ValueError(
            "Datetime comparison failed. Ensure `created_at`, `start`, and `end` "
            "are all either timezone-aware or timezone-naive."
        ) from e
