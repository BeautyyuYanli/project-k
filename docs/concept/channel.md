# Channel Design

## Data model

Structured inputs and memories now use:

- `in_channel: str` (required)
- `out_channel: str | None` (optional)

`out_channel=None` means "same as `in_channel`" for routing and skill selection.

## Channel format

A channel is a URL-path-like hierarchy:

- Slash-separated segments
- No empty segments
- No leading or trailing slash

Example (Telegram thread input):

`telegram/chat/<chat_id>/thread/<message_thread_id>`

## Skill injection

Let `root(channel)` be the first channel segment.

- Context skill: `context/{root(in_channel)}`
- Messager skill: `messager/{root(effective_out_channel)}`
  - `effective_out_channel = out_channel or in_channel`

This keeps routing explicit while reusing platform-level skills.

## Memory retrieval

When retrieving memory for a channel prefix, filter by `MemoryRecord.in_channel`
using prefix matching.

Example:

- Query prefix: `telegram/chat/<chat_id>`
- Matches:
  - `telegram/chat/<chat_id>`
  - `telegram/chat/<chat_id>/thread/1`
  - `telegram/chat/<chat_id>/thread/2`

## Preference injection

For an `in_channel`, inject preferences from root to leaf. For each prefix path
that exists, inject both files in this order:

Preference files are resolved from `~/.kapybara/preferences`.

1. `<prefix>.md`
2. `<prefix>/PREFERENCES.md`

Example for `telegram/chat/<chat_id>`:

1. `telegram.md`
2. `telegram/PREFERENCES.md`
3. `telegram/chat.md`
4. `telegram/chat/PREFERENCES.md`
5. `telegram/chat/<chat_id>.md`
6. `telegram/chat/<chat_id>/PREFERENCES.md`

`by_user`-based preference filtering keeps the current behavior.

## Required Fields

Runtime and retrieval require records/events to use `in_channel` (and optional
`out_channel`).
