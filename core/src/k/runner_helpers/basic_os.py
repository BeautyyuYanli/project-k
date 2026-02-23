"""Helpers for building shell commands in SSH or local PTY mode.

`BasicOSHelper` always builds commands that source
`${K_CONFIG_BASE:-~/.kapybara}/.bashrc`.
When `Config.ssh_user` + `Config.ssh_addr` are configured, commands run over SSH.
When both are `None`, commands run locally via `script -q -c ... /dev/null` to
preserve pseudo-terminal behavior expected by shell-session tools.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from k.config import Config

if TYPE_CHECKING:
    from k.io_helpers.shell import ShellSessionManager

AGENT_CONFIG_BASE_EXPR = "${K_CONFIG_BASE:-~/.kapybara}"
_AGENT_CONFIG_BASE_MARKER = "__KAPY_AGENT_CONFIG_BASE__="


async def agent_config_base_value(
    *,
    basic_os_helper: "BasicOSHelper",
    shell_manager: "ShellSessionManager",
) -> str:
    """Return the current value represented by `AGENT_CONFIG_BASE_EXPR`.

    This resolves in the same shell transport/runtime used by `bash_impl`
    (via `BasicOSHelper.command(...)` + `ShellSessionManager`), so the value
    matches the agent's execution environment instead of Python process env.
    """

    cmd = (
        'if [ -n "${K_CONFIG_BASE:-}" ]; then __kapy_cfg_base="$K_CONFIG_BASE"; '
        "else __kapy_cfg_base=~/.kapybara; fi; "
        f'printf "{_AGENT_CONFIG_BASE_MARKER}%s\\n" "$__kapy_cfg_base"'
    )
    session_id = await shell_manager.new_shell(
        basic_os_helper.command(cmd),
        desc="resolve-agent-config-base",
    )

    stdout, stderr, _ = await shell_manager.next(session_id, timeout_seconds=2)
    merged_output = (stdout + b"\n" + stderr).decode(errors="replace")
    for line in merged_output.splitlines():
        marker_idx = line.find(_AGENT_CONFIG_BASE_MARKER)
        if marker_idx >= 0:
            return line[marker_idx + len(_AGENT_CONFIG_BASE_MARKER) :].strip()

    raise RuntimeError(
        "Could not resolve runtime K_CONFIG_BASE value from shell output"
    )


def single_quote_escape(s: str) -> str:
    return s.replace("'", "'\\''")


def single_quote(s: str) -> str:
    return "'" + single_quote_escape(s) + "'"


@dataclass(slots=True)
class BasicOSHelper:
    """Build shell launcher commands from runtime config."""

    config: Config

    def command_base(self) -> str:
        """Return the transport command prefix for shell execution."""

        if self.config.ssh_user is None or self.config.ssh_addr is None:
            return "script -q -c "
        return (
            "ssh -o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null "
            '-o LogLevel=ERROR -tt -i "'
            f'{self.config.ssh_key!s}" -p {self.config.ssh_port} '
            f"{self.config.ssh_user}@{self.config.ssh_addr} "
        )

    def command(self, command: str, env: dict[str, str] | None = None) -> str:
        """Build the final command including shell bootstrap and env injection.

        Uses `${K_CONFIG_BASE:-~/.kapybara}` for `.bashrc` so shell behavior
        matches the runtime view visible to the agent, even if
        `Config.config_base` points elsewhere in the Python process.
        """

        if env is None:
            env = {}
        payload = (
            f". {AGENT_CONFIG_BASE_EXPR}/.bashrc; "
            + single_quote_escape(
                "".join(
                    f"{key}='{single_quote_escape(value)}'; "
                    for key, value in env.items()
                )
            )
            + single_quote_escape(command)
        )
        wrapped_payload = "'" + payload + "'"
        if self.config.ssh_user is None or self.config.ssh_addr is None:
            return self.command_base() + wrapped_payload + " /dev/null"
        return self.command_base() + wrapped_payload


async def main():
    from k.io_helpers.shell import ShellSession, ShellSessionOptions

    config = Config()
    basic_os_helper = BasicOSHelper(config=config)
    realcommand = basic_os_helper.command("""
bash
python3
    """)
    async with ShellSession(
        realcommand, options=ShellSessionOptions(timeout_seconds=1)
    ) as shell:
        code = None

        stdout, stderr, code = await shell.next()
        while code is None:
            print(stdout.decode(), end="")
            print(stderr.decode(), end="")
            stdout, stderr, code = await shell.next((input("") + "\n").encode())
        print(stdout.decode())
        print(stderr.decode())


if __name__ == "__main__":
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv("core/.env")

    asyncio.run(main())
