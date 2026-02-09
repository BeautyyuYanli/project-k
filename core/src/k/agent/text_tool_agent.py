import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Concatenate, Literal, cast

from pydantic import AfterValidator, BaseModel, BeforeValidator
from pydantic_ai import (
    Agent,
    AgentRunResult,
    FunctionToolset,
    ModelRequest,
    ModelRetry,
    RunContext,
    TextOutput,
    UserPromptPart,
)
from pydantic_ai._run_context import AgentDepsT
from pydantic_ai._tool_manager import ToolManager
from pydantic_ai.exceptions import ToolRetryError
from pydantic_ai.tools import (
    Tool,
    ToolCallPart,
    ToolDefinition,
    ToolParams,
)


def collect_text_tools(tools: Sequence[Tool]) -> str:
    tools_def = ""
    for tool in tools:
        tool_def = cast(ToolDefinition, tool.tool_def)
        tool_def_string = json.dumps(
            {
                "tool_name": tool_def.name,
                "description": tool_def.description,
                "parameters_json_schema": tool_def.parameters_json_schema,
            },
            ensure_ascii=False,
        )
        tools_def += tool_def_string + "\n"
    return tools_def


def get_text_tool_instruction(tools: Sequence[Tool[Any]]) -> str:
    return (
        """
<TextToolInstruction>
Some tools take a long `text` argument. For those tools, do NOT put the long text inside the JSON.

Output exactly one assistant text message in this format:
1) One JSON object: {"tool_name": "...", "arguments": {...}} with all arguments except `text`
   - If `text` is the only argument for the tool, you may omit `arguments`: {"tool_name": "..."}
2) Then the raw text wrapped by markers:
$TextArgStart$
... long text ...
$TextArgEnd$

Example:
{"tool_name": "greeting", "arguments": {"to": "Alice"}}
$TextArgStart$
This is a long text
...Very long text
$TextArgEnd$

Tools that use this format:
"""
        + collect_text_tools(tools)
        + """
</TextToolInstruction>
"""
    )


def create_text_tool_model(tool: Tool):
    class TextToolCall(BaseModel):
        tool_name: Annotated[object, AfterValidator(lambda x: x == tool.name)]
        arguments: Annotated[
            object, BeforeValidator(tool.function_schema.validator.validate_python)
        ]

    return TextToolCall


@dataclass(slots=True)
class Finish[T]:
    data: T


@dataclass(slots=True)
class TextTools[AgentDepsT, T]:
    tools: Sequence[
        Callable[Concatenate[RunContext[AgentDepsT], ToolParams], T]
        | Callable[ToolParams, T]
    ]
    _toolset: FunctionToolset[AgentDepsT] = field(init=False)

    def __post_init__(self):
        self._toolset = FunctionToolset[AgentDepsT](tools=self.tools)

    def text_tool_parser(self, text: str) -> ToolCallPart:
        """
        Parse an assistant tool call with a long `text` argument.

        Supported formats:
        1) Preferred: JSON + markers (long text is outside JSON):
           {"tool_name": "...", "arguments": {...}}  # everything except `text`
           {"tool_name": "..."}  # allowed when `text` is the only argument
           $TextArgStart$
           ... long text ...
           $TextArgEnd$

        2) Fallback (more permissive): a *single* JSON object (no markers).

        Marker errors are reported explicitly to make it easier for the model to
        correct its output.
        """

        text_arg_start = "$TextArgStart$"
        text_arg_end = "$TextArgEnd$"

        def load_tool_call_json(tool_call_json: str) -> dict[str, Any]:
            try:
                tool_call_obj = json.loads(tool_call_json)
            except json.JSONDecodeError as e:
                raise ModelRetry(
                    "Failed to parse the JSON tool call.\n"
                    "Output must start with exactly one JSON object like:\n"
                    '{"tool_name": "...", "arguments": {...}}  # or {"tool_name": "..."} when `text` is the only arg\n'
                    f"JSON error: {e}"
                ) from e
            if not isinstance(tool_call_obj, dict):
                raise ModelRetry(
                    "Invalid JSON tool call: expected a JSON object (dict) at the top level."
                )
            return cast(dict[str, Any], tool_call_obj)

        def parse_json_prefix(tool_call_text: str) -> tuple[dict[str, Any], str]:
            decoder = json.JSONDecoder()
            stripped = tool_call_text.lstrip()
            tool_call_obj, idx = decoder.raw_decode(stripped)
            if not isinstance(tool_call_obj, dict):
                raise ModelRetry(
                    "Invalid JSON tool call: expected a JSON object (dict) at the top level."
                )
            trailing = stripped[idx:].strip()
            return cast(dict[str, Any], tool_call_obj), trailing

        stripped_text = text.strip()
        has_start = text_arg_start in stripped_text
        has_end = text_arg_end in stripped_text

        if has_start or has_end:
            if not has_start:
                raise ModelRetry(
                    f"Found `{text_arg_end}` but missing `{text_arg_start}`.\n"
                    "Expected:\n"
                    '{"tool_name": "...", "arguments": {...}}  # or {"tool_name": "..."} when `text` is the only arg\n'
                    f"{text_arg_start}\n...text...\n{text_arg_end}"
                )
            if not has_end:
                raise ModelRetry(
                    f"Found `{text_arg_start}` but missing `{text_arg_end}`.\n"
                    "Expected:\n"
                    '{"tool_name": "...", "arguments": {...}}  # or {"tool_name": "..."} when `text` is the only arg\n'
                    f"{text_arg_start}\n...text...\n{text_arg_end}"
                )

            json_part, after_start = stripped_text.split(text_arg_start, 1)
            text_part, _trailing = after_start.split(text_arg_end, 1)

            tool_call = load_tool_call_json(json_part.strip())
            tool_name = tool_call.get("tool_name")
            if tool_name is None:
                raise ModelRetry("`tool_name` is missing in the JSON tool call.")
            if not isinstance(tool_name, str):
                raise ModelRetry("`tool_name` must be a string in the JSON tool call.")

            arguments = tool_call.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ModelRetry("`arguments` must be a JSON object (dict).")

            args = dict(cast(dict[str, Any], arguments))
            args["text"] = text_part.strip()
            return ToolCallPart(tool_name=tool_name, args=args)

        # No markers: accept only a single JSON object with `arguments.text`.
        try:
            tool_call, _trailing = parse_json_prefix(stripped_text)
        except json.JSONDecodeError as e:
            raise ModelRetry(
                "Tool call format error.\n"
                "Provide either:\n"
                f"1) JSON + `{text_arg_start}`...`{text_arg_end}` markers, or\n"
                "2) A single JSON object (no markers).\n"
                f"JSON error: {e}"
            ) from e

        tool_name = tool_call.get("tool_name")
        if tool_name is None:
            raise ModelRetry("`tool_name` is missing in the JSON tool call.")
        if not isinstance(tool_name, str):
            raise ModelRetry("`tool_name` must be a string in the JSON tool call.")

        arguments = tool_call.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ModelRetry("`arguments` must be a JSON object (dict).")
        args = dict(cast(dict[str, Any], arguments))
        return ToolCallPart(tool_name=tool_name, args=args)

    async def text_tool_run(self, ctx: RunContext[AgentDepsT], text: str) -> T:
        tool_call_part = self.text_tool_parser(text)
        try:
            res = await (
                await ToolManager(
                    toolset=self._toolset,
                    default_max_retries=0,
                ).for_run_step(ctx=ctx)
            ).handle_call(tool_call_part)
        except ToolRetryError as e:
            raise ModelRetry(str(e)) from e
        return res

    def get_text_tools_instruction(self) -> str:
        return get_text_tool_instruction([v for k, v in self._toolset.tools.items()])


async def agent_run(
    agent: Agent[AgentDepsT, Any], deps: AgentDepsT, user_prompt: str
) -> AgentRunResult[Finish]:
    response = await agent.run(user_prompt, deps=deps)
    while not isinstance(response.output, Finish):
        history = response.all_messages()
        history.append(
            ModelRequest(parts=[UserPromptPart(content=str(response.output))])
        )
        response = await agent.run(
            message_history=response.all_messages(),
            usage=response.usage(),
            metadata=response.metadata,
            deps=deps,
        )
    return response


async def main():
    def edit_file(text: str, file_path: str) -> str:
        """
        Edit the content of a file at the given file path.

        Args:
            text (str): The new content to write to the file.
            file_path (str): The path to the file to be edited.

        """
        with open(file_path, "w") as f:
            f.write(text)
        return f"File at {file_path} has been updated."

    def send_message(text: str) -> Literal["OK"]:
        """
        Send message to the user.
        """
        return "OK"

    def finish_loop() -> Finish[None]:
        """
        Finish the whole process.
        """
        return Finish(None)

    text_tools = TextTools[None, str | type[Finish]](
        tools=[
            edit_file,
            send_message,
            finish_loop,
        ]
    )

    agent = Agent(
        model="openai:gpt-5-chat-latest",
        system_prompt=[
            text_tools.get_text_tools_instruction(),
            "You are a helpful assistant that can edit files on the system.",
        ],
        output_type=TextOutput(text_tools.text_tool_run),
    )

    user_input = 'Edit the file at "./example.txt" to contain the text "Hello, World!" repeated 10 lines'

    await agent_run(agent, deps=None, user_prompt=user_input)


if __name__ == "__main__":
    import asyncio

    import logfire

    logfire.configure()
    logfire.instrument_pydantic_ai()
    asyncio.run(main())
