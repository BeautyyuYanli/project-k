from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic_ai import RunContext

from k.agent.core.shell_tools import bash, bash_wait, edit_file


@dataclass(slots=True)
class _FakeBasicOSHelper:
    def command(self, command: str, env: dict[str, str] | None = None) -> str:
        _ = env
        return command


@dataclass(slots=True)
class _FakeShellManager:
    next_results: list[tuple[bytes, bytes, int | None]] = field(default_factory=list)

    async def new_shell(
        self,
        command: str,
        *,
        options: object | None = None,
        desc: str | None = None,
    ) -> str:
        _ = command, options, desc
        return "000001"

    async def next(
        self, session_id: str, stdin: bytes | None = None
    ) -> tuple[bytes, bytes, int | None]:
        _ = session_id, stdin
        if not self.next_results:
            return b"", b"", 0
        return self.next_results.pop(0)

    async def list_sessions(self) -> list[object]:
        return []

    async def interrupt(self, session_id: str) -> None:
        _ = session_id


@dataclass(slots=True)
class _FakeDeps:
    basic_os_helper: _FakeBasicOSHelper = field(default_factory=_FakeBasicOSHelper)
    shell_manager: _FakeShellManager = field(default_factory=_FakeShellManager)
    bash_cmd_history: list[str] = field(default_factory=list)
    stuck_warning: int = 0
    stuck_warning_limit: int = 3
    count_down: int = 20


def _ctx(deps: _FakeDeps) -> RunContext[_FakeDeps]:
    return cast(RunContext[_FakeDeps], SimpleNamespace(deps=deps))


@pytest.mark.anyio
async def test_bash_wait_appends_progress_reminder_when_countdown_hits_zero() -> None:
    deps = _FakeDeps(count_down=1)
    deps.shell_manager.next_results.append((b"ok\n", b"", 0))

    res = await bash_wait(_ctx(deps), "whatever")
    assert deps.count_down == 0
    assert not isinstance(res, str)
    assert res.system_msg is not None
    assert "progress update" in res.system_msg


@pytest.mark.anyio
async def test_bash_appends_after_existing_system_msg() -> None:
    deps = _FakeDeps(count_down=1)
    deps.shell_manager.next_results.append((b"ok\n", b"", 0))
    deps.bash_cmd_history.append("echo hi")
    deps.stuck_warning = 3
    deps.stuck_warning_limit = 3

    res = await bash(_ctx(deps), "echo hi")
    assert deps.count_down == 0
    assert res.system_msg is not None
    assert res.system_msg.startswith("You seems to be stuck.")
    assert "\nYou've been working for a while." in res.system_msg
    assert "progress update" in res.system_msg


@pytest.mark.anyio
async def test_edit_file_decrements_countdown_only_once() -> None:
    deps = _FakeDeps(count_down=2)
    deps.shell_manager.next_results.append((b"ok\n", b"", 0))

    _ = await edit_file(
        _ctx(deps),
        filename="x.txt",
        old_content="old\n",
        new_content="new\n",
        start_line=1,
    )
    assert deps.count_down == 1
