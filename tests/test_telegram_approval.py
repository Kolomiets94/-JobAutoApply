from unittest.mock import Mock, patch

from telegram_approval import approve


def test_accepts_only_matching_chat_message_and_nonce(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    lead = {"title": "Junior React", "url": "https://example.com/job"}

    def post(url, json, timeout):
        if url.endswith("/sendMessage"):
            nonce = json["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
            get_response.nonce = nonce
            return Mock(json=lambda: {"result": {"message_id": 7}}, raise_for_status=lambda: None)
        return Mock(raise_for_status=lambda: None)

    def get_response(url, params, timeout):
        updates = [
            {"update_id": 1, "callback_query": {"id": "wrong", "data": get_response.nonce,
             "message": {"chat": {"id": 99}, "message_id": 7}}},
            {"update_id": 2, "callback_query": {"id": "right", "data": get_response.nonce,
             "message": {"chat": {"id": 42}, "message_id": 7}}},
        ]
        return Mock(json=lambda: {"result": updates}, raise_for_status=lambda: None)

    with patch("telegram_approval.requests.post", side_effect=post), \
         patch("telegram_approval.requests.get", side_effect=get_response):
        assert approve(lead, "Four sentence draft.")


def test_unconfigured_chat_fails_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert not approve({"title": "Junior React"}, "draft")
