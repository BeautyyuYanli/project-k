"""Core agent implementation.

Public entrypoints:
- `Event`: structured input wrapper used by starters (e.g. Telegram polling).
- `MyDeps`: deps container used by tools/runtime.
- `agent_run`: run the agent and return `(output_json, memory_record)`.
"""

from k.agent.core.agent import MyDeps, agent, agent_run
from k.agent.core.types import Event, MemoryHint, finish_action

__all__ = [
    "Event",
    "MemoryHint",
    "MyDeps",
    "agent",
    "agent_run",
    "finish_action",
]
