import json

from k.starters.telegram import telegram_update_to_event_json


def test_telegram_update_to_event_json_roundtrip() -> None:
    update = {
        "update_id": 123,
        "message": {
            "message_id": 1,
            "from": {"id": 42, "is_bot": False, "first_name": "Alice"},
            "chat": {"id": 99, "type": "private"},
            "date": 1_700_000_000,
            "text": "hello",
        },
    }

    event_json = telegram_update_to_event_json(update)
    event = json.loads(event_json)
    assert event["kind"] == "telegram"

    body = json.loads(event["content"])
    assert body == update
