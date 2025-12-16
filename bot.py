import os
import telebot
import requests
from flask import Flask, request
from telebot import types

# ---------------------------------------------------------
# 1. SETUP - READ VARIABLES FROM RENDER ENVIRONMENT
# ---------------------------------------------------------
API_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL') # Render gives this automatically

# Safety check: If token is missing, print error
if not API_TOKEN:
    print("ERROR: BOT_TOKEN is missing! Add it in Render Environment Variables.")
    
bot = telebot.TeleBot(API_TOKEN)
server = Flask(__name__)
BASE_URL = "https://www.1secmail.com/api/v1/"
user_data = {}

# ---------------------------------------------------------
# 2. EMAIL LOGIC
# ---------------------------------------------------------
def get_random_email():
    try:
        response = requests.get(f"{BASE_URL}?action=genRandomMailbox&count=1", verify=False)
        return response.json()[0] if response.status_code == 200 else None
    except: return None

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

# ---------------------------------------------------------
# 3. BOT COMMANDS
# ---------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📧 Generate New Email", callback_data="generate_email"))
    bot.send_message(message.chat.id, "<b>Temp Mail Bot is Online!</b>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
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
            bot.answer_callback_query(call.id, "API Error. Try again.")

    elif call.data == "check_inbox":
        if chat_id not in user_data:
            bot.answer_callback_query(call.id, "Generate a new email first.")
            return
        login, domain = user_data[chat_id]['login'], user_data[chat_id]['domain']
        msgs = check_email(login, domain)
        if not msgs:
            bot.answer_callback_query(call.id, "Inbox is empty.", show_alert=True)
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

# ---------------------------------------------------------
# 4. SERVER & WEBHOOK SETUP
# ---------------------------------------------------------

# This route receives messages from Telegram
@server.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

# This route runs when you visit the website URL
# IT AUTOMATICALLY RESETS THE WEBHOOK CONNECTION
@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/" + API_TOKEN)
    return "Webhook successfully set! Telegram should work now.", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
