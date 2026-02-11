"""Shared protocol for :class:`k.agent.memory.entities.MemoryRecord` stores.

This module defines the structural interface used by agents to query and append
`MemoryRecord` objects while preserving the parent/child relationship graph.

Design notes / invariants:
- A store is the source of truth for which records exist. Links stored on a
  record (`parents` / `children`) may refer to missing records; link-resolution
  methods support `strict` mode to surface this.
- "Latest" is defined as the most recently appended record id (i.e. the tail of
  the store's append order), not necessarily the max `created_at`.
- `append()` must treat `record.parents` as the source of truth and ensure each
  referenced parent record contains `record.id_` in its `children` list before
  returning.
"""

from __future__ import annotations

from collections.abc import Set
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from k.agent.memory.entities import MemoryRecord

type MemoryRecordId = UUID | str
type MemoryRecordRef = MemoryRecord | UUID | str


def coerce_uuid(value: MemoryRecordId) -> UUID:
    """Coerce a UUID or UUID string into a :class:`uuid.UUID`.

    Raises:
        ValueError: If `value` is not a valid UUID string.
    """

    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except ValueError as e:
        raise ValueError(f"Invalid UUID: {value!r}") from e


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for persisting and querying `MemoryRecord` objects."""

    def refresh(self) -> None:
        """Force a reload from disk (even if the underlying storage did not change)."""

    def get_latest(self) -> UUID | None:
        """Return the latest record id (store append order), or `None` if empty."""

    def get_by_id(self, id_: MemoryRecordId) -> MemoryRecord | None:
        """Return a record by id, or `None` if missing."""

    def get_by_ids(
        self, ids: Set[MemoryRecordId], *, strict: bool = False
    ) -> list[MemoryRecord]:
        """Return records for `ids`, sorted by (`created_at`, store order)."""

    def get_parents(
        self, record: MemoryRecordRef, *, strict: bool = False
    ) -> list[UUID]:
        """Return parent ids for `record` (in the same order as `record.parents`)."""

    def get_children(
        self, record: MemoryRecordRef, *, strict: bool = False
    ) -> list[UUID]:
        """Return child ids for `record` (in the same order as `record.children`)."""

    def get_ancestors(
        self,
        record: MemoryRecordRef,
        *,
        level: int | None = None,
        strict: bool = False,
    ) -> list[UUID]:
        """Return ancestor ids for `record` by repeatedly following parents."""

    def get_between(
        self,
        start: datetime,
        end: datetime,
        *,
        include_start: bool = True,
        include_end: bool = True,
    ) -> list[UUID]:
        """Return record ids whose `created_at` falls within the given range."""

    def append(self, record: MemoryRecord) -> None:
        """Persist `record` and update parents' `children` links."""
