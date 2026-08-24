"""Send a single test alert through the real notification path."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\sunil\Videos\placement tracker\backend")

from services.notification_service import _send_message
from config import settings

async def main():
    print("bot_token set:", bool(settings.telegram_bot_token),
          "| chat_id set:", bool(settings.telegram_chat_id))
    try:
        r = await _send_message(
            "<b>PlacementOS</b> test ping - notifications are working."
        )
        print("SENT OK, message_id:", r and r.get("result", {}).get("message_id"))
    except Exception as e:
        print("SEND FAILED:", type(e).__name__, str(e)[:300])

asyncio.run(main())
