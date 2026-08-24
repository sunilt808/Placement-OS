"""Diagnose Telegram bot: token validity + exact send error."""
import asyncio
import sys
import httpx

sys.path.insert(0, r"C:\Users\sunil\Videos\placement tracker\backend")
from config import settings

API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

async def main():
    async with httpx.AsyncClient(timeout=10) as c:
        me = await c.get(f"{API}/getMe")
        print("getMe:", me.status_code, me.json().get("result", {}).get("username"))
        payload = {"chat_id": settings.telegram_chat_id, "text": "ping"}
        r = await c.post(f"{API}/sendMessage", json=payload)
        print("send status:", r.status_code)
        print("send body:", r.text[:300])
        if r.status_code != 200:
            up = await c.get(f"{API}/getUpdates?limit=5")
            for u in up.json().get("result", [])[-5:]:
                msg = u.get("message") or u.get("channel_post") or {}
                chat = msg.get("chat", {})
                print("recent update from chat:", chat.get("id"), "| type:", chat.get("type"),
                      "| from:", (msg.get("from") or {}).get("username"))

asyncio.run(main())
