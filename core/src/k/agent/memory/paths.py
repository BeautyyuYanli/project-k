"""FolderMemoryStore path helpers.

The runtime keeps persisted memories under the same user-scoped root as other
agent assets (`skills`, `preferences`) so all long-lived state lives under
`<config_base>`.
"""

from __future__ import annotations

from pathlib import Path


def memory_root_from_config_base(config_base: str | Path) -> Path:
    """Return the FolderMemoryStore root directory under `config_base`."""

    return Path(config_base).expanduser().resolve() / "memories"
