"""Helpers for building shell commands in SSH or local PTY mode.

`BasicOSHelper` always builds commands that source `<config_base>/.bashrc`.
When `Config.ssh_user` + `Config.ssh_addr` are configured, commands run over SSH.
When both are `None`, commands run locally via `script -q -c ... /dev/null` to
preserve pseudo-terminal behavior expected by shell-session tools.
"""

from dataclasses import dataclass

from k.config import Config


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
        """Build the final command including shell bootstrap and env injection."""

        if env is None:
            env = {}
        payload = (
            f". {self.config.config_base}/.bashrc; "
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
