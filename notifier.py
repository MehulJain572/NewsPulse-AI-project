import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(TOKEN)

user_responses = {}

def send_approval_request(company, action, score, reason):
    """Sends a professional trade authorization alert to Telegram with buttons."""
    
    markup = InlineKeyboardMarkup()
    yes_btn = InlineKeyboardButton("✅ AUTHORIZE", callback_data=f"yes_{company}")
    no_btn = InlineKeyboardButton("❌ REJECT", callback_data=f"no_{company}")
    markup.add(yes_btn, no_btn)

    message_text = (
        f"⚠️ *NEWSPULSE AI: TRADE AUTHORIZATION REQUIRED* ⚠️\n\n"
        f"🔍 *Target:* {company}\n"
        f"📉 *Negativity Score:* {score}/100\n"
        f"🎯 *Proposed Action:* {action}\n"
        f"📝 *AI Analysis:* {reason}\n\n"
        f"Do you wish to proceed with this trade execution?"
    )

    bot.send_message(CHAT_ID, message_text, parse_mode="Markdown", reply_markup=markup)
    print(f"[NOTIFIER] Alert pushed to mobile for {company}. Waiting for user response...")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data.startswith("yes_"):
        company = call.data.split("_")[1]
        user_responses[company] = "YES"
        bot.answer_callback_query(call.id, "Trade Authorized!")
        bot.edit_message_text(f"✅ Trade for {company} was AUTHORIZED.", CHAT_ID, call.message.message_id)
    
    elif call.data == "no_trade" or call.data.startswith("no_"):
        bot.answer_callback_query(call.id, "Trade Aborted.")
        bot.edit_message_text("❌ Trade was REJECTED by user.", CHAT_ID, call.message.message_id)

def start_listening():
    """Starts the bot listener in the background."""
    bot.infinity_polling()