#!/usr/bin/env python3
"""Edit a file by replacing a known slice of lines.

This script is designed to be invoked from a shell tool where passing long text
via CLI args is inconvenient. Inputs are provided via CLI flags.

Contract:
  - `start_line` is 1-based (like editors).
  - `old_content` must match the file's content starting at `start_line`
    (after normalizing newline style), otherwise the edit fails.
  - On success, the file is rewritten preserving the original file's newline
    style. Trailing-newline presence is preserved unless the edit touches EOF,
    in which case it follows the replacement content (with a special-case for
    deleting the tail, where the last kept line's newline becomes trailing).

Output:
  Prints a human-readable message to stdout and exits with:
    - 0 on success
    - 2 on usage/input errors
    - 3 on edit mismatch
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _detect_newline_style(raw: bytes) -> str:
    if b"\r\n" in raw:
        return "\r\n"
    if b"\r" in raw:
        return "\r"
    return "\n"


@dataclass(frozen=True, slots=True)
class EditResult:
    ok: bool
    filename: str
    start_line: int
    old_line_count: int
    new_line_count: int
    message: str


class EditMismatchError(RuntimeError):
    pass


def apply_edit(
    *, filename: str, start_line: int, old_content: str, new_content: str
) -> EditResult:
    path = Path(filename)
    if start_line < 1:
        raise ValueError("start_line must be >= 1 (1-based line numbers).")

    raw = path.read_bytes()
    newline_style = _detect_newline_style(raw)
    try:
        file_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Best-effort fallback for files with UTF-8 BOM.
        file_text = raw.decode("utf-8-sig")

    file_text_norm = _normalize_newlines(file_text)
    old_norm = _normalize_newlines(old_content)
    new_norm = _normalize_newlines(new_content)

    if file_text_norm == "":
        file_lines: list[str] = []
        file_ends_with_newline = False
    else:
        file_lines = file_text_norm.split("\n")
        file_ends_with_newline = file_text_norm.endswith("\n")
        if file_ends_with_newline and file_lines and file_lines[-1] == "":
            file_lines = file_lines[:-1]

    old_has_trailing_newline = old_norm != "" and old_norm.endswith("\n")
    new_has_trailing_newline = new_norm != "" and new_norm.endswith("\n")

    old_lines = old_norm.split("\n") if old_norm != "" else []
    if old_has_trailing_newline:
        # Mirror the file_lines trimming behavior for consistency.
        if old_lines and old_lines[-1] == "":
            old_lines = old_lines[:-1]

    new_lines = new_norm.split("\n") if new_norm != "" else []
    if new_has_trailing_newline:
        if new_lines and new_lines[-1] == "":
            new_lines = new_lines[:-1]

    start_idx = start_line - 1
    if start_idx > len(file_lines):
        raise ValueError(
            f"start_line {start_line} is beyond EOF (file has {len(file_lines)} lines)."
        )

    end_idx = start_idx + len(old_lines)
    if end_idx > len(file_lines):
        raise EditMismatchError(
            f"old_content expects {len(old_lines)} lines from start_line {start_line}, "
            f"but file has only {len(file_lines) - start_idx} lines remaining."
        )

    existing_slice = file_lines[start_idx:end_idx]
    if existing_slice != old_lines:
        # Provide a small context snippet to help callers recover without dumping huge files.
        ctx_start = max(0, start_idx - 2)
        ctx_end = min(len(file_lines), end_idx + 2)
        context = "\n".join([f"{i + 1}: {file_lines[i]}" for i in range(ctx_start, ctx_end)])
        raise EditMismatchError(
            "old_content mismatch at start_line "
            f"{start_line}.\nContext:\n{context}"
        )

    edit_touches_eof = end_idx == len(file_lines)
    updated_lines = file_lines[:start_idx] + new_lines + file_lines[end_idx:]

    if edit_touches_eof:
        if new_lines:
            updated_ends_with_newline = new_has_trailing_newline
        else:
            # If we deleted the tail and still have prior lines, the newline that used
            # to separate the last kept line from the deleted content becomes trailing.
            updated_ends_with_newline = start_idx > 0
    else:
        updated_ends_with_newline = file_ends_with_newline

    updated_norm = "\n".join(updated_lines)
    if updated_ends_with_newline:
        updated_norm += "\n"

    updated = updated_norm.replace("\n", newline_style)
    path.write_text(updated, encoding="utf-8", newline="")

    return EditResult(
        ok=True,
        filename=str(path),
        start_line=start_line,
        old_line_count=len(old_lines),
        new_line_count=len(new_lines),
        message="updated",
    )


def _parse_args(argv: list[str]) -> tuple[str, int, str, str]:
    # Use argparse's built-in non-exiting mode so we can handle parse errors and
    # keep stdout/exit codes stable for callers.
    parser = argparse.ArgumentParser(prog="edit.py", exit_on_error=False)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--start-line", type=int, required=True)
    parser.add_argument("--old-content", required=True)
    parser.add_argument("--new-content", required=True)
    args = parser.parse_args(argv)

    return (
        str(args.filename),
        int(args.start_line),
        str(args.old_content),
        str(args.new_content),
    )


def _format_ok(result: EditResult) -> str:
    return (
        f"OK: {result.message}\n"
        f"file: {result.filename}\n"
        f"start_line: {result.start_line}\n"
        f"old_lines: {result.old_line_count}\n"
        f"new_lines: {result.new_line_count}"
    )


def _format_error(*, kind: str, message: str) -> str:
    if "\n" in message:
        return f"ERROR ({kind}):\n{message}"
    return f"ERROR ({kind}): {message}"


def main(argv: list[str]) -> int:
    filename = ""
    start_line = 0
    old_content = ""
    new_content = ""
    try:
        filename, start_line, old_content, new_content = _parse_args(argv)
    except Exception as e:
        print(_format_error(kind="usage", message=str(e)))
        return 2

    try:
        res = apply_edit(
            filename=filename,
            start_line=start_line,
            old_content=old_content,
            new_content=new_content,
        )
        print(_format_ok(res))
        return 0
    except EditMismatchError as e:
        payload = EditResult(
            ok=False,
            filename=filename,
            start_line=start_line,
            old_line_count=len(_normalize_newlines(old_content).splitlines())
            if old_content != ""
            else 0,
            new_line_count=len(_normalize_newlines(new_content).splitlines())
            if new_content != ""
            else 0,
            message=str(e),
        )
        details = (
            f"{payload.message}\n"
            f"file: {payload.filename}\n"
            f"start_line: {payload.start_line}\n"
            f"old_lines: {payload.old_line_count}\n"
            f"new_lines: {payload.new_line_count}"
        )
        print(_format_error(kind="mismatch", message=details))
        return 3
    except Exception as e:
        print(_format_error(kind="error", message=str(e)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
