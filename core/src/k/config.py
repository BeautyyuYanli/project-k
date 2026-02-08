from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="K_")

    fs_base: Path
    basic_os_addr: str = "k-container"
    basic_os_port: int = 22
