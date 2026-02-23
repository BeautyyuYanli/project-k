"""`python -m kapy_collections.starters.telegram` entrypoint."""

from __future__ import annotations

import anyio

from . import main

if __name__ == "__main__":
    anyio.run(main)
