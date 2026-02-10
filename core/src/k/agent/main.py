from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext

from k.config import Config
from k.io_helpers.shell import NextResult, ShellSessionInfo, ShellSessionManager
from k.runner_helpers.basic_os import BasicOSHelper, single_quote


@dataclass()
class MyDeps:
    """Dependencies for the agent run.

    Lifecycle:
        `MyDeps` owns a `ShellSessionManager` which may keep subprocesses alive
        across multiple tool calls. Always close it when the deps are no longer
        needed (prefer `async with MyDeps(...)`).
    """

    config: Config
    basic_os_helper: BasicOSHelper = field(init=False)
    shell_manager: ShellSessionManager = field(init=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        self.basic_os_helper = BasicOSHelper(config=self.config)
        self.shell_manager = ShellSessionManager()

    async def __aenter__(self) -> MyDeps:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close resources owned by these deps (idempotent)."""

        if self._closed:
            return
        self._closed = True
        await self.shell_manager.close()


@dataclass(slots=True)
class BashEvent:
    session_id: str
    stdout: str
    stderr: str
    exit_code: int | None = None
    active_sessions: list[ShellSessionInfo] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        session_id: str,
        tpl: NextResult,
        *,
        all_active_sessions: list[ShellSessionInfo],
    ) -> BashEvent:
        stdout, stderr, exit_code = tpl
        return BashEvent(
            session_id=session_id,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            exit_code=exit_code,
            active_sessions=all_active_sessions,
        )


async def bash(
    ctx: RunContext[MyDeps], text: str
) -> BashEvent:
    """
    Start a new bash session with the given commands text.

    Args:
        text: The initial commands text to run in the bash session. The commands can be one line or multiple lines.
    """
    session_id = await ctx.deps.shell_manager.new_shell(
        ctx.deps.basic_os_helper.command(text),
        desc=text[:30] + ("..." if len(text) > 30 else ""),
    )
    res = await ctx.deps.shell_manager.next(session_id)
    active_sessions = await ctx.deps.shell_manager.list_sessions()
    return BashEvent.new(session_id, res, all_active_sessions=active_sessions)


async def bash_input(
    ctx: RunContext[MyDeps], session_id: str, text: str
) -> BashEvent | str:
    """
    Send stdin to a bash session.

    Args:
        session_id: The session id returned by `bash`.
        text: The stdin text to send to the bash session, usually ended with a newline.
    """
    try:
        res = await ctx.deps.shell_manager.next(session_id, stdin=text.encode())
    except KeyError:
        return f"Unknown session id: {session_id}. Start a new session with bash."
    active_sessions = await ctx.deps.shell_manager.list_sessions()
    return BashEvent.new(session_id, res, all_active_sessions=active_sessions)


async def bash_wait(ctx: RunContext[MyDeps], session_id: str) -> BashEvent | str:
    """
    Wait for the next output from a bash session.
    """
    try:
        res = await ctx.deps.shell_manager.next(session_id)
    except KeyError:
        return f"Unknown session id: {session_id}. Start a new session with bash."
    active_sessions = await ctx.deps.shell_manager.list_sessions()
    return BashEvent.new(session_id, res, all_active_sessions=active_sessions)


async def bash_interrupt(ctx: RunContext[MyDeps], session_id: str) -> str:
    """
    Interrupt a bash session. If the session is already ended, do nothing.
    """
    try:
        await ctx.deps.shell_manager.interrupt(session_id)
    except KeyError:
        return f"Unknown session id: {session_id}. Ignored."
    return "Session ended."


async def edit_file(
    ctx: RunContext[MyDeps],
    filename: str,
    start_line: int,
    old_content: str,
    new_content: str,
) -> BashEvent:
    """Edit a file by replacing a known slice of lines.

    Args:
        filename: Target file path (relative or absolute).
        start_line: 1-based line number where `old_content` is expected to start.
        old_content: The exact content expected at `start_line` (normalized for newlines).
        new_content: The replacement content.
    """
    return await bash(
        ctx,
        f"python3 ~/skills/edit/edit.py --filename {single_quote(filename)} --start-line {single_quote(str(start_line))} --old-content {single_quote(old_content)} --new-content {single_quote(new_content)}",
    )


bash_tool_prompt = """
<BashInstruction>
You have access to a Linux machine via bash shell.
You can run commands on the machine using `bash` tools.

`bash` always starts a new session and returns a `session_id`.
Use that `session_id` with `bash_input`/`bash_wait`/`bash_interrupt`.

If `exit_code` is null, the session is still running.
If `exit_code` is an int, the session is finished and closed.
</BashInstruction>
"""

agent = Agent(
    model="openai:gpt-5.2",
    system_prompt=[
        bash_tool_prompt,
        "You are a helpful assistant.",
    ],
    tools=[bash, bash_input, bash_wait, bash_interrupt, edit_file],
    deps_type=MyDeps,
)


async def main():
    config = Config()  # type: ignore
    async with MyDeps(config=config) as my_deps:
        res = await agent.run(
            deps=my_deps,
            # user_prompt="explore the environment. Use the tools concurrently if needed.",
            # user_prompt="Demo your ability to write JSON to a file, and the JSON should contain a long text field with markdown formatting to greeting the user with emojis and other complex style.",
            user_prompt="You should edit `sample.py` to make all things async.",
        )
        print(res.output)


if __name__ == "__main__":
    import anyio
    import logfire
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv("core/.env")

    logfire.configure()
    logfire.instrument_pydantic_ai()
    anyio.run(main)
