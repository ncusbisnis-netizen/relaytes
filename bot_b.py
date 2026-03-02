from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import Update
import redis
import json
import os
import time

redis_client = redis.from_url(os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL')))

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🤖 Relay Bot untuk @bengkelmlbb_bot\n\n"
        "Gunakan: /info [user_id] [zone_id]"
    )

def info_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    if len(args) < 2:
        update.message.reply_text("❌ Format salah!")
        return
    
    request_id = f"req:{user_id}:{chat_id}:{int(time.time())}"
    request_data = {
        'user_id': user_id,
        'chat_id': chat_id,
        'command': '/info',
        'args': args,
        'time': time.time()
    }
    
    redis_client.setex(request_id, 300, json.dumps(request_data))
    redis_client.rpush('pending_requests', request_id)
    
    update.message.reply_text("⏳ Diproses...")

def main():
    updater = Updater(os.environ.get('BOT_B_TOKEN'), use_context=True)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('info', info_command))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
