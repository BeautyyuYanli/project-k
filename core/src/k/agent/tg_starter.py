"""Deprecated module location.

The Telegram starter has moved to :mod:`k.starters.telegram`.
"""

from __future__ import annotations

import anyio

from k.starters.telegram import (  # noqa: F401
    TelegramBotApi,
    TelegramBotApiError,
    chat_group_is_triggered,
    dispatch_groups_for_batch,
    extract_chat_id,
    extract_chat_type,
    extract_update_date_unix_seconds,
    extract_update_id,
    filter_unseen_updates,
    filter_updates_in_time_window,
    group_updates_by_chat_id,
    main,
    telegram_update_to_event,
    telegram_update_to_event_json,
    telegram_updates_to_event,
    update_is_private_chat,
    update_is_reply_to_bot,
    update_matches_keyword,
    update_mentions_bot,
)

if __name__ == "__main__":
    anyio.run(main)
