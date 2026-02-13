---
name: telegram
description: Use curl to call the Telegram Bot API (send/edit/delete messages, media, polling/webhooks).
---

## Upstream dependency (if applicable)
- Upstream: Telegram Bot API
- Official docs: https://core.telegram.org/bots/api
- Current version: (not pinned; refer to docs)
- Skill created: 2026-02-11

# Telegram (Bot API)

Use `curl` to call the **Telegram Bot API**.
The bot token is guaranteed to be set in the env var `${TELEGRAM_BOT_TOKEN}`.

Base URL:

```bash
BASE="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
```

## Core concepts (common)

- **Bot token**: `${TG_BOT_TOKEN}` (keep secret).
- **chat_id**: numeric ID (user / group / channel) or `@channelusername` for public channels.
- **message_id**: ID of a message inside a chat.
- **update**: incoming event delivered by `getUpdates` (polling) or by webhook.
- **Webhook vs polling**:
  - Polling: call `getUpdates` repeatedly (simple, no public URL needed).
  - Webhook: Telegram sends HTTPS POST updates to your server.
- **parse_mode**: `HTML` or `MarkdownV2` for formatting.
- **Entities**: Telegram may return message formatting as `entities` (even if you didn't use `parse_mode`).
- **file_id / files**:
  - When you receive a photo/document/etc you often get a `file_id`.
  - Reuse `file_id` to send the same file again without re-upload.
  - Use `getFile` to obtain a `file_path` for download.
- **Inline keyboards**: `reply_markup` with `inline_keyboard`; button presses arrive as `callback_query`.

## Send a rich-formatted message

```bash
CHAT_ID=123456789

# Use a heredoc to preserve real newlines and avoid most escaping issues
MSG=$(cat <<'HTML'
<b>Hi I'm here!</b> <i>Welcome</i> to the bot message. <u>Have a great day</u>

<b>Today’s Highlights:</b>
• <b>Bold</b>, <i>italic</i>, <code>code</code>
• <a href="https://core.telegram.org/bots/api">Telegram Bot API</a>

<blockquote>Stay curious, stay kind.</blockquote>
HTML
)

curl -sS -X POST "$BASE/sendMessage" \
  -d chat_id="$CHAT_ID" \
  --data-urlencode text="$MSG" \
  -d parse_mode=HTML \
  -d disable_web_page_preview=true
```

## Frequently used APIs

### getMe (sanity check token)

```bash
curl -sS "$BASE/getMe" | jq
```

### sendMessage

Common parameters:
- `chat_id`, `text`
- `parse_mode=HTML|MarkdownV2`
- `disable_web_page_preview=true|false`
- `reply_to_message_id=<message_id>`
- `reply_markup=<json>` (inline keyboard, remove keyboard, force reply)

### editMessageText (edit a sent message)

```bash
CHAT_ID=123
MSG_ID=456
NEW_TEXT="Updated text"

curl -sS -X POST "$BASE/editMessageText" \
  -d chat_id="$CHAT_ID" \
  -d message_id="$MSG_ID" \
  --data-urlencode text="$NEW_TEXT" \
  -d parse_mode=HTML
```

### deleteMessage

```bash
curl -sS -X POST "$BASE/deleteMessage" -d chat_id="$CHAT_ID" -d message_id="$MSG_ID"
```

### sendPhoto / sendDocument (by URL, file_id, or upload)

By URL:

```bash
curl -sS -X POST "$BASE/sendPhoto" \
  -d chat_id="$CHAT_ID" \
  --data-urlencode photo="https://example.com/pic.jpg" \
  --data-urlencode caption="Caption" \
  -d parse_mode=HTML
```

By file upload (multipart):

```bash
curl -sS -X POST "$BASE/sendDocument" \
  -F chat_id="$CHAT_ID" \
  -F document=@"./report.pdf" \
  -F caption="Report" \
  -F parse_mode=HTML
```

### answerCallbackQuery (inline button acknowledgement)

```bash
CALLBACK_ID="<callback_query_id>"

curl -sS -X POST "$BASE/answerCallbackQuery" \
  -d callback_query_id="$CALLBACK_ID" \
  --data-urlencode text="Got it" \
  -d show_alert=false
```

### setWebhook / deleteWebhook

```bash
WEBHOOK_URL="https://your.domain/telegram/webhook"

curl -sS -X POST "$BASE/setWebhook" --data-urlencode url="$WEBHOOK_URL"
# remove webhook (switch back to polling)
curl -sS -X POST "$BASE/deleteWebhook" -d drop_pending_updates=true
```

### getUpdates (polling)

`getUpdates` is **a queue**. If you advance the offset, older updates may no longer be retrievable via `getUpdates`.

To keep this logic out of the doc (and make it repeatable), use the included scripts:

```bash
# Peek (debug): fetch but do NOT advance the offset
~/skills/misc/telegram/get_updates.py --no-consume --out /tmp/tg_updates.json

# Consume: fetch and advance the offset (ack everything you just saw)
~/skills/misc/telegram/get_updates.py --consume --out /tmp/tg_updates.json
```

Defaults:
- Offset file: `${XDG_STATE_HOME:-$HOME/.local/state}/telegram_bot_offset`
- Dump file: `/tmp/tg_updates.json`

Extract the raw update object for a particular message from a dump:

```bash
~/skills/misc/telegram/extract_update.py /tmp/tg_updates.json \
  --chat-id <chat_id> --message-id <message_id>
```

List / filter the most recent messages **from what your bot has received** (Telegram Bot API does not let bots fetch arbitrary chat history):

```bash
# Last 20 messages in a chat (from this dump)
~/skills/misc/telegram/list_messages.py /tmp/tg_updates.json --chat-id <chat_id> --limit 20

# Messages from a specific sender inside that chat
~/skills/misc/telegram/list_messages.py /tmp/tg_updates.json --chat-id <chat_id> --from-id <user_id> --limit 50

# Messages that reply to a given message_id ("reply thread" style)
~/skills/misc/telegram/list_messages.py /tmp/tg_updates.json --chat-id <chat_id> --reply-to <message_id>

# Topic/thread messages (forums): filter by message_thread_id
~/skills/misc/telegram/list_messages.py /tmp/tg_updates.json --chat-id <chat_id> --thread-id <thread_id>
```

Useful field:
- `update_id` (consume by writing `max_update_id + 1` as the next offset)

## reply_markup (inline keyboard) example

```bash
CHAT_ID=123

MARKUP='{"inline_keyboard":[[{"text":"Approve","callback_data":"approve"},{"text":"Reject","callback_data":"reject"}]]}'

curl -sS -X POST "$BASE/sendMessage" \
  -d chat_id="$CHAT_ID" \
  --data-urlencode text="Choose:" \
  -d reply_markup="$MARKUP"
```

## Notes / gotchas

- Prefer `--data-urlencode text=...` so newlines and special characters are encoded correctly.
- Message text supports real newline characters. When building text in shell:
  - **Use a heredoc** (recommended for long messages) to keep text readable and preserve literal newlines.
  - If you keep `MSG='...'` (single quotes), you **cannot** place a literal single-quote inside; and writing `\n` is **two characters** (`\` and `n`), not a newline.
- `MarkdownV2` requires escaping many characters; `HTML` is often simpler.
- Many methods accept either `chat_id`+`message_id` or `inline_message_id` (for inline mode edits).

## Reactions / "点赞" (setMessageReaction)

Telegram Bot API 现在支持给消息加表情反应：`setMessageReaction`。

要点：
- 通过 `chat_id` + `message_id` 定位要点赞的消息。
- `reaction` 参数是 JSON 数组（通常一次 1 个 reaction）。
- bot 不能使用付费 reactions（paid reactions）。
- 想拿到 `message_id`：用 `getUpdates` 拉取最新消息（建议带 `allowed_updates=["message","edited_message"]`），解析出 `result[-1].message.message_id`。

示例（对某条消息点 👍）：

```bash
CHAT_ID=567113516
MESSAGE_ID=898

curl -sS -X POST "$BASE/setMessageReaction" \
  -d chat_id="$CHAT_ID" \
  -d message_id="$MESSAGE_ID" \
  --data-urlencode 'reaction=[{"type":"emoji","emoji":"👍"}]'
```

拉取最新消息并提取 message_id（示例思路）：

```bash
# Save & reuse offset so updates are consumed (won't be returned again)
OFFSET_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/telegram_bot_offset"
export OFFSET_FILE
mkdir -p "$(dirname "$OFFSET_FILE")"
OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)

curl -sS --get "$BASE/getUpdates" \
  --data-urlencode "offset=$OFFSET" \
  --data-urlencode 'limit=5' \
  --data-urlencode 'allowed_updates=["message","edited_message"]' \
  -o /tmp/tg_updates.json

python3 - <<'PY'
import json, os

d=json.load(open('/tmp/tg_updates.json'))
updates=d.get('result',[])
if not updates:
    raise SystemExit(0)

# Print last message info
u=updates[-1]
msg=u.get('message') or u.get('edited_message')
print(msg['chat']['id'], msg['message_id'], msg.get('text',''))

# Consume everything we just saw
max_id=max(x['update_id'] for x in updates)
open(os.environ['OFFSET_FILE'],'w').write(str(max_id+1))
PY
```


