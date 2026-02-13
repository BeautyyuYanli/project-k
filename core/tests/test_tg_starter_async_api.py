import pytest

from k.starters.telegram import TelegramBotApi


@pytest.mark.anyio
async def test_telegram_bot_api_async_wrappers_call_sync_impl(monkeypatch) -> None:
    api = TelegramBotApi(token="test-token")

    got_me_called = False
    got_updates: tuple[int | None, int] | None = None

    def fake_get_me_sync(self):
        nonlocal got_me_called
        got_me_called = True
        return {"id": 123, "username": "MyBot"}

    def fake_get_updates_sync(self, *, offset: int | None, timeout_seconds: int):
        nonlocal got_updates
        got_updates = (offset, timeout_seconds)
        return [{"update_id": 1, "message": {"text": "hi"}}]

    monkeypatch.setattr(TelegramBotApi, "_get_me_sync", fake_get_me_sync)
    monkeypatch.setattr(TelegramBotApi, "_get_updates_sync", fake_get_updates_sync)

    me = await api.get_me()
    assert got_me_called is True
    assert me["id"] == 123

    updates = await api.get_updates(offset=5, timeout_seconds=12)
    assert got_updates == (5, 12)
    assert updates[0]["update_id"] == 1
