import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env_utils import load_local_env
import db
from push_utils import send_push_to_user

load_local_env()

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").strip().lower() == "true"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if TELEGRAM_ENABLED and TOKEN:
    bot = telebot.TeleBot(TOKEN)
else:
    bot = None
    if not TELEGRAM_ENABLED:
        print("[INFO] Telegram disabled via TELEGRAM_ENABLED=false")
    elif not TOKEN:
        print("[WARN] TELEGRAM_BOT_TOKEN missing. Telegram alerts disabled.")

def send_approval_request(user_id, company, action, score, reason, headline="", estimated_value=0):
    user = db.get_user_by_id(user_id)

    push_title = f"AETHER: {action} {company}"
    push_body = f"{'📈' if action == 'BUY' else '📉'} Panic: {score}/100"
    if headline:
        push_body = f"{headline[:80]}… | {push_body}"
    if estimated_value:
        push_body += f" | ₹{estimated_value:,.0f}"

    send_push_to_user(user_id, push_title, push_body)

    request_id = db.create_approval_request(
        user_id, company, headline, action, score, estimated_value, timeout_seconds=120
    )

    if bot is None:
        print(f"[NOTIFIER] Telegram disabled. Push sent to user {user_id} for {company}. Request ID={request_id}")
        return request_id

    if not user or not user.get("telegram_chat_id"):
        print(f"[NOTIFIER] User {user_id} has no Telegram linked. Push sent for {company}. Request ID={request_id}")
        return request_id

    chat_id = user["telegram_chat_id"]
    markup = InlineKeyboardMarkup()
    yes_btn = InlineKeyboardButton("✅ AUTHORIZE", callback_data=f"approve_{request_id}")
    no_btn = InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{request_id}")
    markup.add(yes_btn, no_btn)

    action_emoji = "📈" if action == "BUY" else "📉"
    amount_line = ""
    if estimated_value > 0:
        amount_line = f"💰 *Amount:* ₹{estimated_value:,.0f}\n"

    message_text = (
        f"⚠️ *AETHER: TRADE AUTHORIZATION REQUIRED* ⚠️\n\n"
        f"🔍 *Target:* {company}\n"
        f"📰 *Headline:* {headline}\n"
        f"📉 *Negativity Score:* {score}/100\n"
        f"{action_emoji} *Proposed Action:* {action}\n"
        f"{amount_line}"
        f"📝 *AI Analysis:* {reason}\n\n"
        f"Do you wish to proceed with this trade execution?"
    )

    msg = bot.send_message(chat_id, message_text, parse_mode="Markdown", reply_markup=markup)
    db.update_approval_chat_info(request_id, chat_id, msg.message_id)
    print(f"[NOTIFIER] Telegram + Push sent to user {user_id} for {company}. Request ID={request_id}")
    return request_id


if bot is not None:
    @bot.message_handler(commands=["start"])
    def handle_start(message):
        text = message.text.strip()
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            code = parts[1].strip().upper()
            user = db.get_user_by_linking_code(code)
            if user:
                chat_id = str(message.chat.id)
                db.link_telegram(user["id"], chat_id)
                bot.reply_to(message, (
                    f"✅ Telegram linked to account '{user['username']}'! "
                    f"You'll now receive trade alerts here."
                ))
                return
            bot.reply_to(message, (
                "Invalid or expired link code. "
                "Generate a new one from the web dashboard."
            ))
            return
        bot.reply_to(message, (
            "Welcome to AETHER Trading Agent! 🤖\n\n"
            "This bot sends you real-time trade alerts based on AI analysis "
            "of financial news.\n\n"
            "To link this chat to your web account, use:\n"
            "/link YOUR_CODE\n\n"
            "Get your code from the web dashboard under 'Link Telegram'."
        ))

    @bot.message_handler(commands=["link"])
    def handle_link(message):
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /link YOUR_CODE")
            return

        code = parts[1].strip().upper()
        user = db.get_user_by_linking_code(code)
        if not user:
            bot.reply_to(message, "Invalid or expired code. Generate a new one from the web dashboard.")
            return

        chat_id = str(message.chat.id)
        db.link_telegram(user["id"], chat_id)
        bot.reply_to(message, f"✅ Telegram linked to account '{user['username']}'! You'll now receive trade alerts here.")

    @bot.callback_query_handler(func=lambda call: True)
    def handle_query(call):
        chat_id = str(call.message.chat.id)
        if call.data.startswith("approve_"):
            request_id = int(call.data.split("_", 1)[1])
            req = db.get_approval_request(request_id)
            if not req:
                bot.answer_callback_query(call.id, "Request not found.")
                return
            if str(req.get("chat_id")) != chat_id:
                bot.answer_callback_query(call.id, "Unauthorized.")
                return
            if req["status"] != "pending":
                bot.answer_callback_query(call.id, f"Already {req['status']}.")
                return
            db.update_approval_status(request_id, "approved")
            bot.answer_callback_query(call.id, "Trade Authorized!")
            bot.delete_message(call.message.chat.id, call.message.message_id)

        elif call.data.startswith("reject_"):
            request_id = int(call.data.split("_", 1)[1])
            req = db.get_approval_request(request_id)
            if not req:
                bot.answer_callback_query(call.id, "Request not found.")
                return
            if str(req.get("chat_id")) != chat_id:
                bot.answer_callback_query(call.id, "Unauthorized.")
                return
            if req["status"] != "pending":
                bot.answer_callback_query(call.id, f"Already {req['status']}.")
                return
            db.update_approval_status(request_id, "rejected")
            bot.answer_callback_query(call.id, "Trade Aborted.")
            bot.delete_message(call.message.chat.id, call.message.message_id)

    def start_listening():
        bot.infinity_polling()
