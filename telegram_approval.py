"""Ask the configured Telegram chat to approve each application draft."""

import hashlib
import os
import time
import requests


def approve(lead, proposal):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    url = "https://api.telegram.org/bot" + token + "/"
    nonce = hashlib.sha256((str(lead.get("url")) + proposal + str(time.time())).encode()).hexdigest()[:16]
    text = ("Черновик отклика. Проверьте вакансию, требования и письмо перед отправкой.\n"
            + str(lead.get("title") or "") + "\n" + str(lead.get("url") or "")
            + "\n\n" + proposal)
    try:
        sent = requests.post(url + "sendMessage", json={
            "chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": [[
                {"text": "Подтвердить отправку", "callback_data": "approve:" + nonce},
                {"text": "Отклонить", "callback_data": "reject:" + nonce},
            ]]},
        }, timeout=15)
        sent.raise_for_status()
        message_id = sent.json()["result"]["message_id"]
        print("[telegram-approval] draft delivered", flush=True)
        offset = None
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            payload = {"timeout": 10, "allowed_updates": ["callback_query"]}
            if offset is not None:
                payload["offset"] = offset
            response = requests.get(url + "getUpdates", params=payload, timeout=15)
            response.raise_for_status()
            for update in response.json().get("result", []):
                offset = max(offset or 0, update["update_id"] + 1)
                callback = update.get("callback_query") or {}
                message = callback.get("message") or {}
                data = callback.get("data") or ""
                if (str((message.get("chat") or {}).get("id")) == str(chat_id)
                        and message.get("message_id") == message_id
                        and data in ("approve:" + nonce, "reject:" + nonce)):
                    requests.post(url + "answerCallbackQuery", json={
                        "callback_query_id": callback["id"]}, timeout=10).raise_for_status()
                    print("[telegram-approval] decision received: " +
                          ("approved" if data.startswith("approve:") else "rejected"), flush=True)
                    return data.startswith("approve:")
    except (requests.RequestException, KeyError, ValueError) as exc:
        print("[telegram-approval] failure: " + type(exc).__name__, flush=True)
        return False
    print("[telegram-approval] decision timed out; nothing approved", flush=True)
    return False
