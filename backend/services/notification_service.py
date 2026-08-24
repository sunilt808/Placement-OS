"""
services/notification_service.py — Send formatted Telegram alerts.

Sends rich formatted messages to the student's personal Telegram chat with:
- New placement opportunity alerts with inline action buttons
- Deadline reminders
- Deadline extension notices
- NEEDS_REVIEW alerts (low confidence)
- Daily summary
- Watchdog alerts
"""
import httpx
from typing import Optional
from datetime import datetime

from config import settings
from services.deadline_engine import format_deadline_ist, time_remaining_str

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def _send_message(text: str, reply_markup: Optional[dict] = None, parse_mode: str = "HTML"):
    """Send a message to the student's personal chat.

    Extracted placement text can contain raw <, >, & or unbalanced tags that
    Telegram's HTML parser rejects with HTTP 400. On such a failure the same
    message is retried once WITHOUT parse_mode so delivery never breaks.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        # Notifications are an optional delivery channel; extraction and storage
        # must never fail merely because Telegram has not been configured.
        return None

    async def _post(payload: dict):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        return await _post(payload)
    except httpx.HTTPStatusError as e:
        body = ""
        if e.response is not None:
            body = e.response.text[:200]
            if e.response.status_code == 400 and "chat not found" in body.lower():
                print(
                    "[Notify] CHAT NOT FOUND - open Telegram, search for the bot, "
                    "press START once, and confirm TELEGRAM_CHAT_ID matches your "
                    "numeric user id from @userinfobot."
                )
                raise
        if e.response is not None and e.response.status_code == 400 and parse_mode:
            print("[Notify] HTML parse rejected (400) - retrying as plain text")
            fallback = dict(payload)
            fallback["parse_mode"] = None
            import re as _re
            fallback["text"] = _re.sub(r"</?(?:b|i|u|s|code|pre|a)[^>]*>", "", text)
            return await _post(fallback)
        raise


def _inline_keyboard(opportunity_id: str) -> dict:
    """Inline keyboard for opportunity actions."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Mark Applied", "callback_data": f"applied:{opportunity_id}"},
                {"text": "⏰ Remind Later", "callback_data": f"remind:{opportunity_id}"},
            ],
            [
                {"text": "❌ Ignore", "callback_data": f"ignore:{opportunity_id}"},
                {"text": "📋 View Details", "callback_data": f"view:{opportunity_id}"},
            ],
        ]
    }


async def send_new_opportunity_alert(opp: dict, opportunity_id: str):
    """🚨 NEW PLACEMENT OPPORTUNITY alert."""
    company = opp.get("company") or "Unknown Company"
    role = opp.get("role") or "Role not specified"
    ctc = opp.get("ctc") or "Not specified"
    location = opp.get("location") or "Not specified"
    branches = ", ".join(opp.get("eligible_branches") or []) or "Not specified"
    cgpa = opp.get("cgpa_requirement") or "Not specified"
    deadline = opp.get("deadline")
    reg_link = opp.get("registration_link")
    action_required = opp.get("action_required", False)
    confidence = int(opp.get("confidence", 0) * 100)

    dl_str = format_deadline_ist(deadline) or "Not specified"
    remaining = time_remaining_str(deadline) if deadline else ""

    # Role-first match badge (never branch-gated)
    role_class_labels = {
        "CSE_BOTH": "🎯 PERFECT MATCH — CSE role + CSE/ISE branch",
        "CSE_ROLE": "✅ CSE ROLE MATCH",
        "CSE_BRANCH": "🟡 BRANCH MATCH (role not specified)",
        "NOT_CSE": "⚪ Non-CSE role",
        "UNKNOWN": "❓ Role unknown — verify manually",
    }
    rc = opp.get("role_class")
    badge = f"\n{role_class_labels[rc]}\n" if rc else ""
    form_badge = "📝 <b>GOOGLE FORM REGISTRATION</b>\n" if opp.get("has_registration_form") else ""

    text = f"""🚨 <b>NEW PLACEMENT OPPORTUNITY</b>
{badge}{form_badge}
🏢 <b>Company:</b> {company}
💼 <b>Role:</b> {role}
💰 <b>CTC:</b> {ctc}
📍 <b>Location:</b> {location}

🎓 <b>Eligibility:</b>
  • Branches: {branches}
  • CGPA: {cgpa}

⏰ <b>Deadline:</b> {dl_str}
{f'  <i>({remaining})</i>' if remaining else ''}

{f'🔗 <a href="{reg_link}">Register Here</a>' if reg_link else ''}

⚡ <b>Action Required:</b> {'YES' if action_required else 'NO'}
🤖 <b>AI Confidence:</b> {confidence}%"""

    await _send_message(text, reply_markup=_inline_keyboard(opportunity_id))


async def send_needs_review_alert(opp: dict, opportunity_id: str, original_text: str):
    """⚠️ NEEDS_REVIEW alert for low-confidence extractions."""
    confidence = int(opp.get("confidence", 0) * 100)
    text = f"""⚠️ <b>PLACEMENT MESSAGE — PLEASE REVIEW</b>

<i>AI confidence is low ({confidence}%). May be placement-related.</i>

📝 <b>Summary:</b> {opp.get('summary') or 'Could not summarize'}

📨 <b>Original message:</b>
<blockquote>{original_text[:500]}</blockquote>

Please check this manually."""

    await _send_message(text, reply_markup=_inline_keyboard(opportunity_id))


async def send_reminder(opp: dict, opportunity_id: str, reminder_type: str):
    """⏰ Deadline reminder."""
    type_labels = {
        "THREE_DAYS": "📅 3-DAY REMINDER",
        "TWENTY_FOUR_HOURS": "🔔 24-HOUR REMINDER",
        "THREE_HOURS": "🚨 3-HOUR REMINDER",
    }
    label = type_labels.get(reminder_type, "⏰ REMINDER")
    company = opp.get("company") or "Unknown Company"
    role = opp.get("role") or "Role"
    deadline = opp.get("deadline")
    dl_str = format_deadline_ist(deadline) or "Unknown"
    remaining = time_remaining_str(deadline) if deadline else ""

    text = f"""{label}

🏢 <b>{company}</b> — {role}
⏰ <b>Deadline:</b> {dl_str}
{f'<i>({remaining})</i>' if remaining else ''}

Have you applied yet?"""

    await _send_message(text, reply_markup=_inline_keyboard(opportunity_id))


async def send_deadline_updated(opp: dict, opportunity_id: str, old_deadline, new_deadline):
    """📅 Deadline extension notification."""
    company = opp.get("company") or "Unknown Company"
    old_str = format_deadline_ist(old_deadline) or str(old_deadline)
    new_str = format_deadline_ist(new_deadline) or str(new_deadline)

    text = f"""📅 <b>DEADLINE UPDATED</b>

🏢 <b>{company}</b>

❌ <b>Previous:</b> <s>{old_str}</s>
✅ <b>New Deadline:</b> {new_str}

Reminders have been rescheduled."""

    await _send_message(text, reply_markup=_inline_keyboard(opportunity_id))


async def send_daily_summary(stats: dict):
    """📋 Daily placement summary."""
    text = f"""📋 <b>DAILY PLACEMENT SUMMARY</b>
{datetime.now().strftime('%d %B %Y')}

🔴 <b>Deadline Today:</b> {stats.get('deadline_today', 0)}
🟠 <b>Deadline Tomorrow:</b> {stats.get('deadline_tomorrow', 0)}
🟡 <b>This Week:</b> {stats.get('this_week', 0)}
🟢 <b>Upcoming:</b> {stats.get('upcoming', 0)}

⚠️ <b>Not Applied:</b> {stats.get('not_applied', 0)}
✅ <b>Applied:</b> {stats.get('applied', 0)}
📊 <b>Total Active:</b> {stats.get('active', 0)}"""

    await _send_message(text)


async def send_watchdog_alert(message: str):
    """🚨 Watchdog/system alert."""
    text = f"🚨 <b>SYSTEM ALERT</b>\n\n{message}"
    await _send_message(text)


async def send_shortlist_hit_alert(company, filename: str, hit: dict, opportunity_id: str):
    """🎉 YOU ARE SHORTLISTED — fired when the student's identity is found in a result sheet."""
    row_preview = " | ".join(v for v in hit.get("row", [])[:8] if v)
    text = f"""🎉🎉 <b>SHORTLIST ALERT — CHECK NOW</b> 🎉🎉

✅ <b>YOUR {hit['matched_field']} WAS FOUND IN A RESULT SHEET!</b>

🏢 <b>Drive:</b> {company or 'Unknown (check dashboard)'}
📎 <b>Sheet:</b> {filename}
🔎 <b>Matched:</b> {hit['matched_field']} → "{hit['cell_text']}" (row {hit['row_number']})
{f'<code>{row_preview[:300]}</code>' if row_preview else ''}

⚠️ Follow next steps in the placement group IMMEDIATELY."""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Mark Applied", "callback_data": f"applied:{opportunity_id}"},
                {"text": "📋 View Details", "callback_data": f"view:{opportunity_id}"},
            ],
        ]
    }
    await _send_message(text, reply_markup=keyboard)


async def send_import_complete(stats: dict):
    """📥 Historical import complete notification."""
    text = f"""📥 <b>HISTORICAL IMPORT COMPLETE</b>

📨 Messages found: {stats.get('total', 0)}
🔍 Pre-filtered: {stats.get('prefiltered', 0)}
🤖 Sent to AI: {stats.get('ai_processed', 0)}
💼 Placement messages: {stats.get('placement', 0)}
✨ Opportunities created: {stats.get('created', 0)}
🔄 Existing updated: {stats.get('updated', 0)}
🔁 Duplicates merged: {stats.get('duplicates', 0)}
⚫ Possible missed: {stats.get('missed', 0)}"""

    await _send_message(text)


async def send_storage_alert(used_mb: float, limit_mb: int, percent: float,
                             collections: dict | None = None):
    """Cloud-storage warning when nearing the free-tier quota."""
    top = ""
    if collections:
        ranked = sorted(collections.items(),
                        key=lambda kv: kv[1].get("mb", 0), reverse=True)[:3]
        top = "\n".join(
            f"• {name}: {v.get('mb', 0)} MB ({v.get('count', 0)} docs)"
            for name, v in ranked)
        top = f"\n<b>Heaviest collections</b>\n{top}\n"
    text = (
        "💾 <b>STORAGE WARNING</b>\n\n"
        f"Database: <b>{used_mb} MB / {limit_mb} MB</b> ({percent}%)\n"
        f"{top}\n"
        "Open the app and delete old drives/messages, or wait for the "
        f"{getattr(__import__('config').settings, 'data_retention_days', 25)}"
        "-day auto-purge to clear stale data."
    )
    await _send_message(text)
