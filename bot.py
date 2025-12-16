import telebot
import requests
import os
from flask import Flask, request
from telebot import types

# --- SETUP ---
# MAKE SURE YOUR REAL TOKEN IS HERE
API_TOKEN = "8240002422:AAEbpCsYuRzN4JK5WaMdakfmUoBjfwCbRoo"

bot = telebot.TeleBot(API_TOKEN)
server = Flask(__name__)
BASE_URL = "https://www.1secmail.com/api/v1/"
user_data = {}

# --- EMAIL LOGIC ---
def get_random_email():
    try:
        response = requests.get(f"{BASE_URL}?action=genRandomMailbox&count=1", verify=False)
        return response.json()[0]
    except: return None

def check_email(login, domain):
    try:
        response = requests.get(f"{BASE_URL}?action=getMessages&login={login}&domain={domain}", verify=False)
        return response.json()
    except: return []

def read_message(login, domain, message_id):
    try:
        response = requests.get(f"{BASE_URL}?action=readMessage&login={login}&domain={domain}&id={message_id}", verify=False)
        return response.json()
    except: return None

# --- BOT COMMANDS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📧 Generate New Email", callback_data="generate_email"))
    bot.reply_to(message, "Temp Mail Bot is Online!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if call.data == "generate_email":
        email = get_random_email()
        if email:
            login, domain = email.split('@')
            user_data[chat_id] = {'login': login, 'domain': domain}
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Check Inbox", callback_data="check_inbox"))
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"Email: {email}", reply_markup=markup)
    
    elif call.data == "check_inbox":
        if chat_id in user_data:
            msgs = check_email(user_data[chat_id]['login'], user_data[chat_id]['domain'])
            if not msgs: bot.answer_callback_query(call.id, "Inbox empty", show_alert=True)
            else: bot.send_message(chat_id, f"Found {len(msgs)} emails.")

# --- SIMPLIFIED SERVER ---
# This accepts traffic sent to ANY url path, fixing the 404 error
@server.route('/<path:path>', methods=['POST'])
def getMessage(path):
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

# Root page check
@server.route("/")
def webhook():
    return "Bot is running!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
