"""Application runtime configuration.

`config_base` is the canonical filesystem root for Kapybara state. It points
to the `.kapybara` directory itself (for example: `./data/fs/.kapybara`).
"""

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Settings loaded from constructor kwargs and `K_*` environment variables.

    Invariant:
        `config_base` always points at the `.kapybara` directory.
        `ssh_key` is normalized to an absolute path at init time and is
        not interpreted relative to `config_base`.
        `ssh_user` and `ssh_addr` are configured together for SSH mode, or both
        are `None` to enable local command execution mode.
    """

    model_config = SettingsConfigDict(env_prefix="K_")

    config_base: Path = Path("~/.kapybara")
    ssh_user: str | None = None
    ssh_addr: str | None = None
    ssh_port: int = 22
    ssh_key: Path = Path("~/.ssh/id_ed25519")

    @field_validator("config_base", "ssh_key")
    @classmethod
    def _normalize_path_settings(cls, value: Path) -> Path:
        """Normalize path-like settings to absolute paths."""

        return value.expanduser().resolve()

    @model_validator(mode="after")
    def _validate_ssh_target(self) -> "Config":
        """Require both SSH endpoint parts or neither.

        When both are `None`, command execution falls back to local mode.
        """

        if (self.ssh_user is None) ^ (self.ssh_addr is None):
            raise ValueError(
                "ssh_user and ssh_addr must either both be set or both be None"
            )
        return self
