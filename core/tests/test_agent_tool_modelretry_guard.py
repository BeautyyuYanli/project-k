from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from k.agent.core.agent import _tool_model_retry_guard


@pytest.mark.anyio
async def test_tool_model_retry_guard_wraps_unexpected_exceptions() -> None:
    async def boom(ctx: object) -> str:
        raise ValueError("nope")

    guarded = _tool_model_retry_guard(boom)
    ctx = SimpleNamespace(tool_name="boom")

    with pytest.raises(ModelRetry) as exc_info:
        await guarded(ctx)  # type: ignore[arg-type]

    msg = str(exc_info.value)
    assert "boom" in msg
    assert "ValueError" in msg


@pytest.mark.anyio
async def test_tool_model_retry_guard_passes_through_modelretry() -> None:
    async def already_retry(ctx: object) -> None:
        raise ModelRetry("try again")

    guarded = _tool_model_retry_guard(already_retry)
    ctx = SimpleNamespace(tool_name="already_retry")

    with pytest.raises(ModelRetry) as exc_info:
        await guarded(ctx)  # type: ignore[arg-type]

    assert str(exc_info.value) == "try again"
