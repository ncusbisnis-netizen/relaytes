from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import redis
import json
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL'))
redis_client = redis.from_url(REDIS_URL)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start"""
    await update.message.reply_text(
        "🤖 *Relay Bot untuk @bengkelmlbb_bot*\n\n"
        "Gunakan perintah:\n"
        "/info [user_id] [zone_id]\n"
        "Contoh: /info 643461181 8554",
        parse_mode='Markdown'
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /info"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Format salah!\n"
            "Gunakan: /info [user_id] [zone_id]"
        )
        return
    
    request_id = f"req:{user_id}:{chat_id}:{int(time.time())}"
    
    request_data = {
        'user_id': user_id,
        'chat_id': chat_id,
        'command': '/info',
        'args': args,
        'status': 'pending',
        'time': time.time()
    }
    
    # Simpan ke Redis
    redis_client.setex(request_id, 300, json.dumps(request_data))
    redis_client.rpush('pending_requests', request_id)
    
    await update.message.reply_text(
        f"⏳ *Memproses request...*\n"
        f"User ID: `{args[0]}`\n"
        f"Zone ID: `{args[1]}`\n\n"
        f"Tunggu sebentar...",
        parse_mode='Markdown'
    )
    
    logger.info(f"📤 Request dari {user_id}: /info {' '.join(args)}")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /ping"""
    await update.message.reply_text("pong")

def main():
    """Jalankan bot"""
    # Dapatkan token dari environment
    token = os.environ.get('BOT_B_TOKEN')
    if not token:
        logger.error("BOT_B_TOKEN tidak ditemukan di environment!")
        return
    
    # Buat aplikasi (cara baru python-telegram-bot v20+)
    application = Application.builder().token(token).build()
    
    # Tambahkan handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('info', info_command))
    application.add_handler(CommandHandler('ping', ping))
    
    logger.info("✅ Bot B started!")
    
    # Jalankan bot
    application.run_polling()

if __name__ == '__main__':
    main()
