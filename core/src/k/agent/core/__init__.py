"""Core agent implementation.

Public entrypoints:
- `Event`: structured input wrapper used by starters (e.g. Telegram polling).
- `MyDeps`: deps container used by tools/runtime.
- `agent_run`: run the agent and return a `MemoryRecord`.
"""

from k.agent.core.agent import MyDeps, agent, agent_run, finish_action
from k.agent.core.entities import Event, MemoryHint

__all__ = [
    "Event",
    "MemoryHint",
    "MyDeps",
    "agent",
    "agent_run",
    "finish_action",
]
