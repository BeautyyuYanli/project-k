from dataclasses import dataclass

from k.config import Config


@dataclass(slots=True)
class BasicOSHelper:
    config: Config

    def command_base(self) -> str:
        return f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -tt -i "{self.config.fs_base!s}/{self.config.basic_os_sshkey!s}" -p {self.config.basic_os_port} {self.config.basic_os_user}@{self.config.basic_os_addr} '

    def command(self, command: str) -> str:
        return (
            f"{self.command_base()} '{command.replace("'", "'").replace('\\', '\\\\')}'"
        )

    def bash_command_non_interactive(self, command: str) -> str:
        return f"{self.command_base()} bash -s <<'K_EOF'\n{command}\nK_EOF"


async def main():
    from k.io_helpers.shell import ShellSession

    config = Config(_env_file=".env")  # type: ignore
    basic_os_helper = BasicOSHelper(config=config)
    realcommand = basic_os_helper.command("""
bash
python3
    """)
    async with ShellSession(realcommand, timeout_seconds=1) as shell:
        code = None

        stdout, stderr, code = await shell.next()
        while code is None:
            print(stdout.decode())
            print(stderr.decode())
            stdout, stderr, code = await shell.next((input("> ") + "\n").encode())
        print(stdout.decode())
        print(stderr.decode())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
