import os
import telebot
import requests
from telebot import types
from flask import Flask, request

# 1. SETUP VARIABLES
# We get the token from Render's Environment Variables
API_TOKEN = os.environ.get('8291407561:AAHjfxzVoCvO81RBqJsvZ6hL2UKjv24NqFs')
# We get the Render URL automatically later
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL') 

bot = telebot.TeleBot(API_TOKEN)
server = Flask(__name__)
BASE_URL = "https://www.1secmail.com/api/v1/"
user_data = {}

# --- BOT LOGIC (SAME AS BEFORE) ---

def get_random_email():
    response = requests.get(f"{BASE_URL}?action=genRandomMailbox&count=1")
    return response.json()[0] if response.status_code == 200 else None

def check_email(login, domain):
    response = requests.get(f"{BASE_URL}?action=getMessages&login={login}&domain={domain}")
    return response.json() if response.status_code == 200 else []

def read_message(login, domain, message_id):
    response = requests.get(f"{BASE_URL}?action=readMessage&login={login}&domain={domain}&id={message_id}")
    return response.json() if response.status_code == 200 else None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📧 Generate New Email", callback_data="generate_email"))
    bot.send_message(message.chat.id, "<b>Welcome to Temp Mail Bot!</b>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "generate_email":
        email_address = get_random_email()
        if email_address:
            login, domain = email_address.split('@')
            user_data[chat_id] = {'login': login, 'domain': domain}
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Check Inbox", callback_data="check_inbox"),
                       types.InlineKeyboardButton("📧 New Address", callback_data="generate_email"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"<b>Email:</b> <code>{email_address}</code>", parse_mode='HTML', reply_markup=markup)

    elif call.data == "check_inbox":
        if chat_id not in user_data:
            bot.answer_callback_query(call.id, "Session expired.")
            return
        login, domain = user_data[chat_id]['login'], user_data[chat_id]['domain']
        messages = check_email(login, domain)
        if not messages:
            bot.answer_callback_query(call.id, "Inbox is empty.", show_alert=True)
        else:
            markup = types.InlineKeyboardMarkup()
            for msg in messages:
                markup.add(types.InlineKeyboardButton(f"📩 {msg['subject'][:15]}...", callback_data=f"read_{msg['id']}"))
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="check_inbox"),
                       types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"Inbox for {login}@{domain}: {len(messages)} msgs", parse_mode='HTML', reply_markup=markup)

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

    elif call.data == "back_to_main":
        if chat_id in user_data:
            login, domain = user_data[chat_id]['login'], user_data[chat_id]['domain']
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Check Inbox", callback_data="check_inbox"),
                       types.InlineKeyboardButton("📧 New Address", callback_data="generate_email"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"<b>Email:</b> <code>{login}@{domain}</code>", parse_mode='HTML', reply_markup=markup)

# --- WEBHOOK CONFIGURATION ---

@server.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/" + API_TOKEN)
    return "Bot is running!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
