from k.config import Config
from dataclasses import dataclass


@dataclass(slots=True)
class BasicOSHelper:
    config: Config

    def command_base(self) -> str:
        return f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -T  -i "{str(self.config.fs_base)}/.ssh/id_ed25519" -p {self.config.basic_os_port} k@{self.config.basic_os_addr} '
    
    def command(self, command: str) -> str:
        return self.command_base() + command
    
    def bash_command_non_interactive(self, command: str) -> str:
        return f"{self.command_base()} bash -s <<'K_EOF'\n{command}\nK_EOF"

