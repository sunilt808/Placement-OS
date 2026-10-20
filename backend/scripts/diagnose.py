"""
scripts/diagnose.py — One-shot health check for the whole notification chain.

Run locally:
    & ".venv\\Scripts\\python.exe" scripts/diagnose.py          (from backend/)

Checks, in order:
  1. Config presence (bot token, chat id, session, group, DB, Gemini)
  2. Telegram bot token validity (getMe)
  3. Whether the configured chat id can actually receive (sendMessage)
  4. Which chats have recently talked to the bot (getUpdates) — reveals the
     real chat id when the configured one is wrong
  5. MongoDB reachability
  6. Gemini model reachability (optional)

Exit code is non-zero if alert delivery is broken, so it can gate deploys.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from config import settings  # noqa: E402

OK = "[OK]"
WARN = "[!]"
BAD = "[X]"


def _line(label: str, ok: bool, detail: str = "", warn: bool = False):
    mark = OK if ok else (WARN if warn else BAD)
    print(f"  {mark} {label}" + (f" - {detail}" if detail else ""))
    return ok


async def check_config() -> bool:
    print("\n[1] Configuration")
    all_ok = True
    all_ok &= _line("TELEGRAM_BOT_TOKEN", bool(settings.telegram_bot_token))
    all_ok &= _line("TELEGRAM_CHAT_ID", bool(settings.telegram_chat_id),
                    settings.telegram_chat_id or "empty")
    _line("TELEGRAM_SESSION_STRING (userbot)", bool(settings.telegram_session_string),
          warn=True)
    _line("PLACEMENT_GROUP_ID (userbot)", settings.placement_group_id is not None,
          str(settings.placement_group_id), warn=True)
    _line("MONGODB_URI", bool(settings.mongodb_uri))
    _line("GEMINI_API_KEY", bool(settings.gemini_api_key), warn=True)
    return all_ok


async def check_bot() -> bool:
    if not settings.telegram_bot_token:
        print("\n[2] Telegram bot — skipped (no token)")
        return False
    api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=15) as c:
        print("\n[2] Telegram bot token")
        r = await c.get(f"{api}/getMe")
        me = r.json().get("result", {}) if r.status_code == 200 else {}
        if not _line("getMe", r.status_code == 200,
                     f"@{me.get('username')}" if me else r.text[:120]):
            return False

        print("\n[3] Alert delivery (sendMessage)")
        payload = {"chat_id": settings.telegram_chat_id,
                   "text": "PlacementOS diagnostic ping"}
        sr = await c.post(f"{api}/sendMessage", json=payload)
        delivered = sr.status_code == 200
        if delivered:
            _line("delivered to configured chat", True, settings.telegram_chat_id)
        else:
            desc = ""
            try:
                desc = sr.json().get("description", "")
            except Exception:
                desc = sr.text[:120]
            _line("delivered to configured chat", False, desc)

        if not delivered:
            print("\n[4] Recent chats that messaged the bot (via getUpdates)")
            up = await c.get(f"{api}/getUpdates?limit=100")
            results = up.json().get("result", []) if up.status_code == 200 else []
            seen = {}
            for u in results:
                msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
                chat = msg.get("chat") or {}
                if chat.get("id") is not None:
                    seen[chat["id"]] = chat.get("first_name") or chat.get("title") or chat.get("type")
            if seen:
                print("      Found ids — set TELEGRAM_CHAT_ID to the correct one:")
                for cid, name in seen.items():
                    print(f"        • {cid}  ({name})")
            else:
                print(f"      No updates found. {WARN} Open @{me.get('username')} in "
                      f"Telegram and press START, then re-run this script.")
        return delivered


async def check_db() -> bool:
    print("\n[5] MongoDB")
    try:
        from database import connect_db, close_db, is_db_ready
        connected = await connect_db(retries=2, delay=1.0)
        _line("reachable", connected, settings.mongodb_db if connected else "")
        await close_db()
        return connected
    except Exception as e:
        return _line("reachable", False, f"{type(e).__name__}: {e}")


async def check_gemini() -> bool:
    print("\n[6] Gemini (optional)")
    if not settings.gemini_api_key or not settings.gemini_enabled:
        print(f"  {WARN} skipped (disabled or no key)")
        return True
    try:
        from services.ai_service import _gemini_client
        if not _gemini_client:
            return _line("client", False, "not initialised")
        resp = await asyncio.to_thread(
            _gemini_client.models.generate_content,
            model=settings.gemini_flash_model,
            contents="Reply with OK",
        )
        text = (getattr(resp, "text", "") or "").strip()
        return _line("model reachable", bool(text),
                     f"{settings.gemini_flash_model}: {text[:40]}")
    except Exception as e:
        return _line("model reachable", False, f"{type(e).__name__}: {e}")


async def main():
    print("=" * 62)
    print(" PlacementOS Diagnostic")
    print("=" * 62)
    cfg = await check_config()
    bot = await check_bot()
    db = await check_db()
    await check_gemini()

    print("\n" + "=" * 62)
    if cfg and bot and db:
        print(f"{OK} Core chain healthy — you should receive alerts.")
        print("=" * 62)
        return 0
    print(f"{BAD} Issues found above. Fix the {BAD} items first.")
    if not bot:
        print("   → Most likely: TELEGRAM_CHAT_ID is wrong, or you never "
              "pressed START in your bot.")
    print("=" * 62)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
