"""Shared Pydantic models for the agent core.

Keep these types isolated from the agent wiring so they can be imported by
tools, deps, and runners without creating import cycles.
"""

from __future__ import annotations

from pydantic import BaseModel


class Event(BaseModel):
    kind: str
    content: str


class MemoryHint(BaseModel):
    referenced_memory_ids: list[str]
    from_where_and_response_to_where: str
    user_intents: str
    action_summary: str


def finish_action(
    referenced_memory_ids: list[str],
    from_where_and_response_to_where: str,
    user_intents: str,
    action_summary: str,
) -> MemoryHint:
    """
    Final structured output for the agent run

    Args:
        referenced_memory_ids: Memory record IDs that were used as context. Can be empty.
        from_where_and_response_to_where: Description of the input sources and response destinations (channel, app, IDs, etc.).
        user_intents: The interpreted intent(s) of the user. If there are multiple intents,
            include them all (e.g. as a short numbered/bulleted list in one string).
        action_summary: A concise summary of actions taken, in
            a way that is useful for logging and future context.
    """

    return MemoryHint(
        referenced_memory_ids=referenced_memory_ids,
        from_where_and_response_to_where=from_where_and_response_to_where,
        user_intents=user_intents,
        action_summary=action_summary,
    )
