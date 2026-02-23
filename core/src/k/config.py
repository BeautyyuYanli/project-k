"""Application runtime configuration.

`config_base` is the canonical filesystem root for Kapybara state. It points
to the `.kapybara` directory itself (for example: `./data/fs/.kapybara`).
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Settings loaded from constructor kwargs and `K_*` environment variables.

    Invariant:
        `config_base` always points at the `.kapybara` directory.
        `basic_os_sshkey` is normalized to an absolute path at init time and is
        not interpreted relative to `config_base`.
    """

    model_config = SettingsConfigDict(env_prefix="K_")

    config_base: Path = Path("~/.kapybara")
    basic_os_user: str = "k"
    basic_os_addr: str = "k-container"
    basic_os_port: int = 22
    basic_os_sshkey: Path = Path("~/.ssh/id_ed25519")

    @field_validator("config_base", "basic_os_sshkey")
    @classmethod
    def _normalize_path_settings(cls, value: Path) -> Path:
        """Normalize path-like settings to absolute paths."""

        return value.expanduser().resolve()
