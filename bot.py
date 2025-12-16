import os
import logging
import telebot
import requests
from flask import Flask, request
from telebot import types

# --- 1. CONFIGURATION & LOGGING ---
# Enable logging to see errors in Render logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load variables
API_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL') # Auto-filled by Render

# Initialize Bot
# threaded=False is CRITICAL for Render/Flask stability
bot = telebot.TeleBot(API_TOKEN, threaded=False)
server = Flask(__name__)

BASE_URL = "https://www.1secmail.com/api/v1/"
user_data = {}

# --- 2. EMAIL FUNCTIONS ---
def get_random_email():
    try:
        # verify=False prevents SSL errors
        response = requests.get(f"{BASE_URL}?action=genRandomMailbox&count=1", verify=False)
        return response.json()[0] if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Error generating email: {e}")
        return None

def check_email(login, domain):
    try:
        response = requests.get(f"{BASE_URL}?action=getMessages&login={login}&domain={domain}", verify=False)
        return response.json() if response.status_code == 200 else []
    except: return []

def read_message(login, domain, message_id):
    try:
        response = requests.get(f"{BASE_URL}?action=readMessage&login={login}&domain={domain}&id={message_id}", verify=False)
        return response.json() if response.status_code == 200 else None
    except: return None

# --- 3. BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Received /start from {message.chat.id}") # LOGGING
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📧 Generate New Email", callback_data="generate_email"))
    bot.reply_to(message, "<b>Temp Mail Bot is Online!</b>\nSystem: Render Cloud", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    logger.info(f"Button clicked: {call.data}") # LOGGING
    
    if call.data == "generate_email":
        email = get_random_email()
        if email:
            login, domain = email.split('@')
            user_data[chat_id] = {'login': login, 'domain': domain}
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Check Inbox", callback_data="check_inbox"),
                       types.InlineKeyboardButton("📧 New Address", callback_data="generate_email"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"<b>Email:</b> <code>{email}</code>", parse_mode='HTML', reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Error contacting Email API.")

    elif call.data == "check_inbox":
        if chat_id not in user_data:
            bot.answer_callback_query(call.id, "Session expired.")
            return
        login, domain = user_data[chat_id]['login'], user_data[chat_id]['domain']
        msgs = check_email(login, domain)
        if not msgs:
            bot.answer_callback_query(call.id, "Inbox empty.", show_alert=True)
        else:
            markup = types.InlineKeyboardMarkup()
            for msg in msgs:
                markup.add(types.InlineKeyboardButton(f"📩 {msg['subject'][:15]}...", callback_data=f"read_{msg['id']}"))
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="check_inbox"),
                       types.InlineKeyboardButton("📧 New", callback_data="generate_email"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"Inbox for {login}@{domain}: {len(msgs)} msgs", parse_mode='HTML', reply_markup=markup)

    elif call.data.startswith("read_"):
        if chat_id not in user_data: return
        msg_id = call.data.split("_")[1]
        login, domain = user_data[chat_id]['login'], user_data[chat_id]['domain']
        full_msg = read_message(login, domain, msg_id)
        if full_msg:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="check_inbox"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"From: {full_msg['from']}\nSub: {full_msg['subject']}\n\n{full_msg.get('textBody', 'No text')[:3000]}", 
                parse_mode='HTML', reply_markup=markup)

# --- 4. FLASK ROUTES ---

# Simpler Route: Just /webhook
# This reduces the chance of URL mismatch errors
@server.route('/webhook', methods=['POST'])
def webhook_handler():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Forbidden", 403

# DEBUG PAGE & SETUP TRIGGER
@server.route("/")
def index():
    # Force Remove & Set Webhook again to be 100% sure
    bot.remove_webhook()
    
    # Construct the URL
    # We use the simplified /webhook path
    target_url = f"{RENDER_URL}/webhook"
    
    # Set it
    try:
        bot.set_webhook(url=target_url)
        status = f"✅ SUCCESS! Webhook set to: {target_url}"
    except Exception as e:
        status = f"❌ ERROR setting webhook: {e}"

    return f"""
    <h1>Bot Status</h1>
    <p><b>Render URL:</b> {RENDER_URL}</p>
    <p><b>Target Webhook:</b> {target_url}</p>
    <p><b>Setup Status:</b> {status}</p>
    <hr>
    <p>Go to Telegram and search for your bot now.</p>
    """, 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
