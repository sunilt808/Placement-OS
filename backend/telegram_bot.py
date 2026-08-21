"""
telegram_bot.py — Bot API backup + command bot.

Role (from revised plan):
- PRIMARY: Telethon userbot listens passively to the group.
- THIS BOT (backup): Handles manually forwarded messages + bot commands.

Commands:
  /start, /help, /jobs, /today, /urgent, /deadlines,
  /applied, /pending, /expired, /stats, /search <company>

Callback handlers:
  applied:<id>   → mark as APPLIED
  ignore:<id>    → mark as IGNORED
  remind:<id>    → remind in 1 hour
  view:<id>      → show details
"""
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from bson import ObjectId
import pytz

from config import settings
from database import opportunities_col, messages_col
from models.message import MessageSource
from models.opportunity import ApplicationStatus
from services.message_pipeline import ingest_message
from services.reminder_service import cancel_all_reminders, schedule_reminders
from services.deadline_engine import format_deadline_ist, time_remaining_str, get_urgency
from services.notification_service import send_daily_summary
from services.opportunity_engine import detect_missed_opportunities

IST = pytz.timezone("Asia/Kolkata")
AUTHORIZED_CHAT_ID = int(settings.telegram_chat_id) if settings.telegram_chat_id.isdigit() else None


def _auth_check(update: Update) -> bool:
    return AUTHORIZED_CHAT_ID is not None and update.effective_chat.id == AUTHORIZED_CHAT_ID


# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    await update.message.reply_text(
        "👋 <b>AI Placement Monitor</b>\n\n"
        "I'm watching your placements. Forward any placement message here.\n\n"
        "Commands:\n"
        "/jobs — All active opportunities\n"
        "/today — Deadlines today\n"
        "/urgent — Urgent (within 24h)\n"
        "/deadlines — Upcoming deadlines\n"
        "/applied — Applied opportunities\n"
        "/pending — Not yet applied\n"
        "/stats — Statistics\n"
        "/search <company> — Search by company",
        parse_mode="HTML"
    )


async def cmd_jobs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    col = opportunities_col()
    cursor = col.find(
        {"status": {"$nin": ["IGNORED", "EXPIRED"]}},
        sort=[("created_at", -1)],
        limit=10,
    )
    lines = ["💼 <b>Active Opportunities</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        company = opp.get("company") or "Unknown"
        role = opp.get("role") or "Role N/A"
        urgency = get_urgency(opp.get("deadline"))
        urgency_emoji = {"TODAY": "🔴", "WITHIN_24H": "🔴", "TOMORROW": "🟠",
                        "WITHIN_3_DAYS": "🟡", "THIS_WEEK": "🟡", "UPCOMING": "🟢",
                        "EXPIRED": "⚫", "NO_DEADLINE": "⚪"}.get(urgency, "⚪")
        lines.append(f"{urgency_emoji} <b>{company}</b> — {role}")

    if not count:
        await update.message.reply_text("No active opportunities found.", parse_mode="HTML")
        return
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)
    col = opportunities_col()
    cursor = col.find({
        "deadline": {"$gte": now.replace(tzinfo=None), "$lt": tomorrow.replace(tzinfo=None)},
        "status": {"$nin": ["APPLIED", "IGNORED"]},
    })
    lines = ["🔴 <b>Deadlines TODAY</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        dl_str = format_deadline_ist(opp.get("deadline")) or "?"
        lines.append(f"• <b>{opp.get('company')}</b> — {dl_str}")
    if not count:
        lines.append("No deadlines today! 🎉")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_urgent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)
    col = opportunities_col()
    cursor = col.find({
        "deadline": {"$gte": now.replace(tzinfo=None), "$lt": cutoff.replace(tzinfo=None)},
        "status": {"$nin": ["APPLIED", "IGNORED"]},
    })
    lines = ["🚨 <b>URGENT — Next 24 Hours</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        remaining = time_remaining_str(opp.get("deadline"))
        lines.append(f"• <b>{opp.get('company')}</b> — {remaining}")
    if not count:
        lines.append("No urgent deadlines! ✅")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_applied(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    col = opportunities_col()
    cursor = col.find({"status": "APPLIED"}, sort=[("updated_at", -1)], limit=10)
    lines = ["✅ <b>Applied Opportunities</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        lines.append(f"• <b>{opp.get('company')}</b> — {opp.get('role') or 'N/A'}")
    if not count:
        lines.append("No applied opportunities yet.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    col = opportunities_col()
    cursor = col.find(
        {"status": {"$in": ["NEW", "VIEWED", "NOT_APPLIED"]}},
        sort=[("deadline", 1)], limit=10
    )
    lines = ["⏳ <b>Pending — Not Applied Yet</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        remaining = time_remaining_str(opp.get("deadline"))
        lines.append(f"• <b>{opp.get('company')}</b> — {remaining}")
    if not count:
        lines.append("Nothing pending!")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_expired(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    missed = await detect_missed_opportunities()
    lines = ["⚫ <b>Possible Missed Opportunities</b>\n"]
    if not missed:
        lines.append("No missed opportunities detected! 🎉")
    for opp in missed[:10]:
        dl_str = format_deadline_ist(opp.get("deadline")) or "Unknown"
        lines.append(f"• <b>{opp.get('company')}</b> — Deadline was: {dl_str}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    col = opportunities_col()
    total = await col.count_documents({})
    applied = await col.count_documents({"status": "APPLIED"})
    pending = await col.count_documents({"status": {"$in": ["NEW", "VIEWED", "NOT_APPLIED"]}})
    ignored = await col.count_documents({"status": "IGNORED"})
    msgs_total = await messages_col().count_documents({})

    await update.message.reply_text(
        f"📊 <b>Statistics</b>\n\n"
        f"💼 Total Opportunities: {total}\n"
        f"✅ Applied: {applied}\n"
        f"⏳ Pending: {pending}\n"
        f"❌ Ignored: {ignored}\n"
        f"📨 Total Messages Processed: {msgs_total}",
        parse_mode="HTML"
    )


async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth_check(update):
        return
    query = " ".join(ctx.args).strip()
    if not query:
        await update.message.reply_text("Usage: /search <company name>")
        return
    col = opportunities_col()
    cursor = col.find(
        {"company": {"$regex": query, "$options": "i"}},
        sort=[("created_at", -1)], limit=5
    )
    lines = [f"🔍 <b>Search: {query}</b>\n"]
    count = 0
    async for opp in cursor:
        count += 1
        dl_str = format_deadline_ist(opp.get("deadline")) or "No deadline"
        lines.append(f"• <b>{opp.get('company')}</b> — {opp.get('role') or 'N/A'} | {dl_str}")
    if not count:
        lines.append("No matches found.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── Message handler — forwarded messages go through pipeline ──────────────────

async def handle_forwarded(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Process manually forwarded messages (backup ingestion path)."""
    if not _auth_check(update):
        return
    text = update.message.text or update.message.caption or ""
    if not text.strip():
        await update.message.reply_text("⚠️ No text found in this message.")
        return

    # Use original forward date if available, else now
    fwd_date = update.message.forward_date
    msg_date = fwd_date if fwd_date else update.message.date
    if msg_date.tzinfo is None:
        msg_date = IST.localize(msg_date)

    await update.message.reply_text("🔄 Processing...")
    opp_id = await ingest_message(
        text=text,
        message_date=msg_date,
        source=MessageSource.BOT_FORWARD,
        telegram_message_id=update.message.message_id,
    )
    if opp_id:
        await update.message.reply_text(
            f"✅ Processed! Opportunity saved.\n"
            f"View in dashboard: http://localhost:5173/opportunities/{opp_id}"
        )
    else:
        await update.message.reply_text("ℹ️ Message processed — not classified as placement-related.")


# ── Callback Query Handler — inline button actions ────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    action, _, opp_id = data.partition(":")
    col = opportunities_col()

    try:
        obj_id = ObjectId(opp_id)
    except Exception:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "applied":
        await col.update_one({"_id": obj_id}, {"$set": {"status": "APPLIED"}})
        await cancel_all_reminders(opp_id)
        await query.edit_message_text(
            query.message.text + "\n\n✅ <b>Marked as APPLIED</b>",
            parse_mode="HTML"
        )

    elif action == "ignore":
        await col.update_one({"_id": obj_id}, {"$set": {"status": "IGNORED"}})
        await cancel_all_reminders(opp_id)
        await query.edit_message_text(
            query.message.text + "\n\n❌ <b>Ignored</b>",
            parse_mode="HTML"
        )

    elif action == "remind":
        # Remind in 1 hour
        remind_time = datetime.now(timezone.utc) + timedelta(hours=1)
        from database import reminders_col
        from models.message import ReminderType
        await reminders_col().insert_one({
            "opportunity_id": opp_id,
            "reminder_type": ReminderType.CUSTOM,
            "scheduled_time": remind_time.replace(tzinfo=None),
            "sent": False,
            "sent_at": None,
            "cancelled": False,
        })
        await query.answer("⏰ Reminder set for 1 hour from now!")

    elif action == "view":
        opp = await col.find_one({"_id": obj_id})
        if opp:
            dl_str = format_deadline_ist(opp.get("deadline")) or "Not specified"
            text = (
                f"📋 <b>{opp.get('company')}</b>\n"
                f"Role: {opp.get('role') or 'N/A'}\n"
                f"CTC: {opp.get('ctc') or 'N/A'}\n"
                f"Deadline: {dl_str}\n"
                f"Status: {opp.get('status')}\n"
                f"Link: {opp.get('registration_link') or 'N/A'}"
            )
            await query.message.reply_text(text, parse_mode="HTML")


# ── App builder ───────────────────────────────────────────────────────────────

def build_bot_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("urgent", cmd_urgent))
    app.add_handler(CommandHandler("deadlines", cmd_urgent))  # Alias
    app.add_handler(CommandHandler("applied", cmd_applied))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("expired", cmd_expired))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_forwarded))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app
