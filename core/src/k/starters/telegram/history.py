"""Persistence helpers for Telegram starter updates and dispatch state.

This module stores raw Telegram updates as JSON Lines (one JSON object per
line), reads the latest updates per chat id, and persists per-chat trigger
cursors used by the polling runner.

Design notes / invariants:
- The update log is append-only and ordered by arrival time.
- Stored update objects are raw Telegram updates (not compacted event payloads).
- `load_recent_updates_grouped_by_chat_id()` preserves per-chat chronological
  order while keeping only the latest `N` updates for each chat id.
- Trigger cursor state maps `chat_id -> last_triggered_update_id` and is
  serialized as JSON with string keys for stable cross-language compatibility.
"""

from __future__ import annotations

import json
import tempfile
from collections import deque
from pathlib import Path
from typing import Any

from .compact import extract_chat_id

_TRIGGER_STATE_VERSION = 1


def append_updates_jsonl(path: Path, updates: list[dict[str, Any]]) -> int:
    """Append raw Telegram updates to a JSONL file.

    Args:
        path: Destination JSONL path. Parent directories are created when needed.
        updates: Raw updates to append, one JSON object per line.

    Returns:
        Number of appended updates.

    Side effects:
    - Creates parent directories for `path`.
    - Appends to `path` using UTF-8.
    """

    if not updates:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with path.open("a", encoding="utf-8") as f:
        for update in updates:
            f.write(json.dumps(update, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
            written += 1
    return written


def load_recent_updates_grouped_by_chat_id(
    path: Path,
    *,
    per_chat_limit: int,
) -> dict[int | None, list[dict[str, Any]]]:
    """Load latest updates from JSONL storage and group by chat id.

    Args:
        path: JSONL update log path.
        per_chat_limit: Maximum updates kept per chat id. Must be > 0.

    Returns:
        A mapping of `chat_id -> list[updates]` with each list in chronological
        order. Updates without chat id are grouped under `None`.

    Raises:
        ValueError: If `per_chat_limit <= 0` or any non-empty line in `path` is
            not a valid JSON object.
    """

    if per_chat_limit <= 0:
        raise ValueError(f"per_chat_limit must be > 0; got {per_chat_limit}")
    if not path.exists():
        return {}

    grouped: dict[int | None, deque[dict[str, Any]]] = {}

    with path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                update = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {e}") from e
            if not isinstance(update, dict):
                raise ValueError(
                    f"Invalid update object at {path}:{line_no}: expected JSON object"
                )

            chat_id = extract_chat_id(update)
            bucket = grouped.get(chat_id)
            if bucket is None:
                bucket = deque(maxlen=per_chat_limit)
                grouped[chat_id] = bucket
            bucket.append(update)

    return {chat_id: list(bucket) for chat_id, bucket in grouped.items()}


def trigger_cursor_state_path_for_updates_store(updates_store_path: Path) -> Path:
    """Return the trigger-cursor state path for a given updates JSONL path."""

    return updates_store_path.with_name(
        updates_store_path.name + ".trigger_cursor_state.json"
    )


def load_last_trigger_update_id_by_chat(path: Path) -> dict[int, int]:
    """Load persisted trigger cursor state.

    Args:
        path: Trigger-state JSON file path.

    Returns:
        Mapping `chat_id -> last_triggered_update_id`. Missing files return `{}`.

    Raises:
        ValueError: If the file is invalid JSON or has invalid schema.
    """

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON at {path}: {e}") from e

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid trigger state at {path}: expected JSON object")
    version = payload.get("version")
    if version != _TRIGGER_STATE_VERSION:
        raise ValueError(
            f"Invalid trigger state version at {path}: expected {_TRIGGER_STATE_VERSION}, got {version!r}"
        )

    raw_map = payload.get("last_trigger_update_id_by_chat")
    if not isinstance(raw_map, dict):
        raise ValueError(
            f"Invalid trigger state at {path}: missing last_trigger_update_id_by_chat object"
        )

    out: dict[int, int] = {}
    for raw_chat_id, raw_update_id in raw_map.items():
        try:
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid trigger state at {path}: invalid chat id key {raw_chat_id!r}"
            ) from e
        if not isinstance(raw_update_id, int) or raw_update_id < 0:
            raise ValueError(
                f"Invalid trigger state at {path}: invalid update id for chat {raw_chat_id!r}"
            )
        out[chat_id] = raw_update_id

    return out


def save_last_trigger_update_id_by_chat(path: Path, by_chat: dict[int, int]) -> None:
    """Persist trigger cursor state atomically.

    Args:
        path: Trigger-state JSON file path.
        by_chat: Mapping `chat_id -> last_triggered_update_id` to persist.

    Side effects:
    - Creates parent directories for `path`.
    - Atomically replaces `path` via temporary file + rename.

    Raises:
    - ValueError: If `by_chat` contains invalid values.
    """

    encoded: dict[str, int] = {}
    for chat_id, update_id in by_chat.items():
        if not isinstance(update_id, int) or update_id < 0:
            raise ValueError(
                f"Invalid trigger cursor for chat_id={chat_id!r}: {update_id!r}"
            )
        encoded[str(chat_id)] = update_id

    payload = {
        "version": _TRIGGER_STATE_VERSION,
        "last_trigger_update_id_by_chat": dict(
            sorted(encoded.items(), key=lambda kv: int(kv[0]))
        ),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = path.parent if path.parent.exists() else None
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=tmp_dir,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tf:
        tmp_path = Path(tf.name)
        tf.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        tf.write("\n")

    tmp_path.replace(path)
