from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_ai.models import KnownModelName, Model


async def create_memory_record(
    compacted: list[str],
) -> list[str]:
    return compacted


compact_agent = Agent(
    system_prompt="""You are a helpful AI agent. 
Your job is to compact the given memory into a list of concise messages,
where each message captures the essence of one or more original messages.

The `Inbound` means messages from outside, and the `Outbound` means messages from AI (yourself).
""",
    output_type=create_memory_record,
)


def print_detailed(detailed: list[ModelRequest | ModelResponse]):
    res = ""
    for msg in detailed:
        if isinstance(msg, ModelRequest):
            res += f"Inbound: {msg.parts!r}\n"
        else:
            res += f"Outbound: {msg.parts!r}\n"
    return res


async def run_compaction(
    model: Model | KnownModelName,
    detailed: list[ModelRequest | ModelResponse],
):
    compacted = await compact_agent.run(
        model=model,
        user_prompt=print_detailed(detailed),
    )
    return compacted.output


async def main():
    from rich import print

    with open("mem.jsonl", encoding="utf-8") as f:
        lines = f.read()

    res = await compact_agent.run(
        model="openai:gpt-5-chat-latest",
        user_prompt=lines,
    )
    print(res.output)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
