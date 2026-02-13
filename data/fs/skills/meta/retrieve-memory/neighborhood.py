#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Print a memory neighborhood (related records) from the local ~/memories store.

A record’s “neighborhood” is all records reachable from a starting record by
following `parents` and/or `children` links up to N steps (inclusive), plus the
starting record itself.

- Traverses both directions (`parents` and `children`).
- Uses a single level bound (max BFS depth).
- Prints results as NDJSON.
- Sorts results by id (which is chronological for this id scheme).
- If present, merges `*.compacted.json` sidecar files into the output records as
  the `compacted` field (JSON array of strings).

Example output line:
  {"id_":"AZxS4r6O","parents":[],"children":["AZxS5E8z"],...}
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import deque
from typing import Any


def build_index(root: str) -> dict[str, str]:
    index: dict[str, str] = {}
    pat = os.path.join(os.path.expanduser(root), "**/*.json")
    for p in glob.glob(pat, recursive=True):
        if p.endswith(".compacted.json"):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                j = json.load(f)
            mid = j.get("id_") or j.get("id")
            if mid:
                mid_str = str(mid)
                prev = index.get(mid_str)
                if prev is None:
                    index[mid_str] = p
                elif prev.endswith(".core.json"):
                    # Prefer core records over legacy "<id>.json" if both exist.
                    pass
                elif p.endswith(".core.json"):
                    index[mid_str] = p
        except Exception:
            continue
    return index


def _compacted_sidecar_path(record_path: str) -> str:
    if record_path.endswith(".core.json"):
        return record_path[: -len(".core.json")] + ".compacted.json"
    if record_path.endswith(".json") and not record_path.endswith(".compacted.json"):
        return record_path[: -len(".json")] + ".compacted.json"
    return record_path + ".compacted.json"


def load_record(index: dict[str, str], mid: str) -> dict[str, Any] | None:
    p = index.get(mid)
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            rec = json.load(f)
    except Exception:
        return None

    if not isinstance(rec, dict):
        return None

    # Newer stores keep `compacted` in a sibling `*.compacted.json` sidecar.
    if "compacted" not in rec:
        sidecar = _compacted_sidecar_path(p)
        try:
            with open(sidecar, "r", encoding="utf-8") as f:
                compacted = json.load(f)
            if isinstance(compacted, list) and all(
                isinstance(item, str) for item in compacted
            ):
                rec["compacted"] = compacted
        except Exception:
            pass

    return rec


def related(index: dict[str, str], start: str, max_depth: int) -> dict[str, int]:
    """Return {id: depth} for all nodes reachable within max_depth (inclusive)."""

    depths: dict[str, int] = {start: 0}
    q: deque[str] = deque([start])

    while q:
        cur = q.popleft()
        d = depths[cur]
        if d == max_depth:
            continue

        rec = load_record(index, cur)
        if not rec:
            continue

        for edge in ("parents", "children"):
            for nxt in rec.get(edge, []) or []:
                nxt = str(nxt)
                nd = d + 1
                if nxt in depths and depths[nxt] <= nd:
                    continue
                if nd > max_depth:
                    continue
                depths[nxt] = nd
                q.append(nxt)

    return depths


def main() -> int:
    # Argparse treats tokens starting with '-' as options, even when they are
    # values to a flag. Memory ids can start with '-' (by design), so normalize
    # common invocations into the unambiguous "--id=<value>" form before parsing.
    argv = list(sys.argv[1:])

    def is_known_flag(token: str) -> bool:
        return token in {"-h", "--help", "-n", "--levels", "--id"}

    if argv and argv[0].startswith("-") and not is_known_flag(argv[0]):
        argv[0] = f"--id={argv[0]}"

    if "--id" in argv:
        idx = argv.index("--id")
        if idx + 1 < len(argv) and argv[idx + 1].startswith("-") and not is_known_flag(
            argv[idx + 1]
        ):
            argv[idx] = f"--id={argv[idx + 1]}"
            del argv[idx + 1]

    ap = argparse.ArgumentParser(
        description=(
            "Print a memory neighborhood: the base id plus all ancestors/descendants within N levels, sorted by id (chronological)."
        )
    )
    ap.add_argument(
        "id",
        nargs="?",
        help=(
            "Base memory id (e.g. AZxSw9mW). If the id begins with '-', prefer using --id to avoid argparse treating it as an option."
        ),
    )
    ap.add_argument(
        "--id",
        dest="id_flag",
        help="Base memory id (recommended; works even if the id begins with '-').",
    )
    ap.add_argument(
        "-n",
        "--levels",
        type=int,
        default=3,
        help="Max BFS depth (levels) to expand in both directions.",
    )
    args = ap.parse_args(argv)

    start_id = args.id_flag or args.id
    if not start_id:
        ap.error("id is required (use --id if it begins with '-')")

    index = build_index("~/memories/records")
    depths = related(index, start_id, args.levels)

    for mid in sorted(depths.keys()):
        rec = load_record(index, mid)
        if rec is None:
            continue
        print(json.dumps(rec, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
