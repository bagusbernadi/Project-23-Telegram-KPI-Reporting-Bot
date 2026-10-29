import pytest
from bot.sender import DryRunSender, SendError, TelegramSender


def test_dry_run_logs():
    s = DryRunSender()
    s.send("halo", "daily", "2026-03-30 07:00:00", "2026-03-27")
    assert s.log[0]["status"] == "sent" and s.messages[0]["text"] == "halo"


def test_retry_then_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    calls, waits = [], []

    def post(url, data, files=None):
        calls.append(url)
        if len(calls) < 3:
            raise SendError("boom TOK")
    t = TelegramSender(post=post, sleep=waits.append)
    assert t.send("x", "daily", "t", "d") and len(calls) == 3 and waits == [2, 5]


def test_token_masked_on_failure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOK123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

    def post(url, data, files=None):
        raise SendError("gagal https://api.telegram.org/botTOK123/sendMessage")
    t = TelegramSender(post=post, sleep=lambda s: None)
    assert not t.send("x", "daily", "t", "d")
    assert t.log[-1]["status"] == "failed" and "TOK123" not in t.log[-1]["error"]


def test_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SendError):
        TelegramSender(post=lambda *a, **k: None).send("x", "daily", "t", "d")
