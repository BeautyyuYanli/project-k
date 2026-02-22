"""FolderMemoryStore path helpers.

The runtime keeps persisted memories under the same user-scoped root as other
agent assets (`skills`, `preferences`) so all long-lived state lives under
`<fs_base>/.kapybara`.
"""

from __future__ import annotations

from pathlib import Path


def memory_root_from_fs_base(fs_base: str | Path) -> Path:
    """Return the FolderMemoryStore root directory under `fs_base`."""

    return Path(fs_base).expanduser().resolve() / ".kapybara" / "memories"
