from pyrogram import Client, filters
from pyrogram.types import Message
import redis
import json
import os
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config dari environment
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')  # YANG BQ... INI!
BOT_B_TOKEN = os.environ.get('BOT_B_TOKEN')
BOT_A_CHAT_ID = int(os.environ.get('BOT_A_CHAT_ID'))
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL'))

# Redis connection
r = redis.from_url(REDIS_URL)

# Pyrogram Client dengan session string ANDA
app = Client(
    name="relay_bot",
    session_string=SESSION_STRING,  # PAKAI SESSION BQ... ANDA!
    api_id=API_ID,
    api_hash=API_HASH
)

bot_status = {'in_captcha': False}

@app.on_message(filters.chat(BOT_A_CHAT_ID))
async def handle_bot_reply(client, message: Message):
    """Handle balasan dari Bot A"""
    text = message.text or message.caption or ''
    
    # Cek captcha
    if message.photo and ('captcha' in text.lower() or 'verify' in text.lower()):
        logger.warning("🚫 CAPTCHA DETECTED!")
        bot_status['in_captcha'] = True
        # TODO: OCR captcha
        await asyncio.sleep(60)
        bot_status['in_captcha'] = False
        return
    
    # Forward ke user
    if not bot_status['in_captcha']:
        request_id = r.lpop('pending_requests')
        if request_id:
            request_id = request_id.decode('utf-8')
            request_data = json.loads(r.get(request_id))
            
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            try:
                requests.post(url, json={
                    'chat_id': request_data['chat_id'],
                    'text': text
                })
                logger.info(f"✅ Forwarded to user {request_data['chat_id']}")
            except Exception as e:
                logger.error(f"Forward error: {e}")
                r.rpush('pending_requests', request_id)

@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    await message.reply("✅ Relay aktif!")

async def process_queue():
    """Queue processor"""
    while True:
        if not bot_status['in_captcha']:
            request_id = r.lpop('pending_requests')
            if request_id:
                request_id = request_id.decode('utf-8')
                request_data = json.loads(r.get(request_id))
                
                cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                await app.send_message(BOT_A_CHAT_ID, cmd)
                logger.info(f"📤 Request: {cmd}")
                r.setex(request_id, 300, json.dumps(request_data))
        
        await asyncio.sleep(3)

async def main():
    await app.start()
    logger.info("✅ Userbot started!")
    await process_queue()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
