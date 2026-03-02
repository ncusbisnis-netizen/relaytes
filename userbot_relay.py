import requests
import asyncio
import os
import time
import re
import logging
import json
import redis
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler, RawUpdateHandler
import pytesseract
from PIL import Image, ImageEnhance

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config dari environment
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')
BOT_B_TOKEN = os.environ.get('BOT_B_TOKEN', '')
BOT_A_CHAT_ID = int(os.environ.get('BOT_A_CHAT_ID', 0))
BOT_A_USERNAME = os.environ.get('BOT_A_USERNAME', 'bengkelmlbb_bot')
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))

# Validasi environment
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, BOT_A_CHAT_ID, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    exit(1)

# Redis connection
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

# Pyrogram Client
app = Client(
    name="relay_bot",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
    workers=8,
    sleep_threshold=30
)

bot_status = {'in_captcha': False}
sent_requests = {}

# ==================== OCR FUNCTION ====================

async def read_number_from_photo(photo_message):
    """Baca angka 6 digit dari foto captcha"""
    try:
        logger.info("📸 Downloading captcha photo...")
        photo_path = await photo_message.download()
        
        img = Image.open(photo_path)
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.point(lambda p: p > 200 and 255)
        
        temp_path = f"/tmp/ocr_{int(time.time())}.png"
        img.save(temp_path)
        
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        
        os.remove(photo_path)
        os.remove(temp_path)
        
        text = re.sub(r'[^0-9]', '', text)
        match = re.search(r'(\d{6})', text)
        
        if match:
            code = match.group(1)
            logger.info(f"✅ OCR success: {code}")
            return code
        return None
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

# ==================== ULTRA SENSITIVE MESSAGE HANDLER ====================

@app.on_message()
async def ultra_sensitive_handler(client, message: Message):
    """
    Handler yang menangkap SEMUA pesan APAPUN, dari SIAPAPUN,
    dengan cara APAPUN (reply, biasa, forward, dll)
    """
    # ========== LOG SUPER LENGKAP ==========
    logger.info("=" * 80)
    logger.info("🔥🔥🔥 ULTRA SENSITIVE HANDLER TRIGGERED 🔥🔥🔥")
    logger.info(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📌 Message ID: {message.id}")
    logger.info(f"💬 Chat ID: {message.chat.id}")
    logger.info(f"💬 Chat Type: {message.chat.type}")
    logger.info(f"👤 From User ID: {message.from_user.id if message.from_user else 'None'}")
    logger.info(f"👤 From Username: @{message.from_user.username if message.from_user and message.from_user.username else 'None'}")
    logger.info(f"👤 From First Name: {message.from_user.first_name if message.from_user else 'None'}")
    logger.info(f"👤 From Last Name: {message.from_user.last_name if message.from_user else 'None'}")
    logger.info(f"🤖 Is Bot: {message.from_user.is_bot if message.from_user else 'N/A'}")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"🎥 Has Video: {bool(message.video)}")
    logger.info(f"📄 Has Document: {bool(message.document)}")
    logger.info(f"🔊 Has Audio: {bool(message.audio)}")
    logger.info(f"📊 Has Media Group: {bool(message.media_group_id)}")
    logger.info(f"🔘 Has Reply Markup: {bool(message.reply_markup)}")
    
    # Text dari mana pun
    text = ""
    if message.text:
        text = message.text
        logger.info(f"📝 Text from message.text: '{text}'")
    elif message.caption:
        text = message.caption
        logger.info(f"📝 Text from message.caption: '{text}'")
    
    logger.info(f"📝 Text length: {len(text)}")
    logger.info(f"📝 Text preview: '{text[:200]}'")
    
    # Reply info
    if message.reply_to_message:
        logger.info(f"↩️ This is a REPLY to message ID: {message.reply_to_message.id}")
        if message.reply_to_message.from_user:
            logger.info(f"↩️ Replying to user: {message.reply_to_message.from_user.id}")
    
    # Forward info
    if message.forward_from:
        logger.info(f"↪️ Forward From: {message.forward_from.id} - @{message.forward_from.username}")
    if message.forward_from_chat:
        logger.info(f"↪️ Forward From Chat: {message.forward_from_chat.id}")
    
    # Service message
    if message.service:
        logger.info(f"🛠️ Service message: {message.service}")
    
    # ========== CEK APAKAH INI DARI BOT A (MULTI LEVEL) ==========
    is_from_bot_a = False
    match_reason = []
    
    # Level 1: Chat ID match
    if message.chat.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append(f"Chat ID = {BOT_A_CHAT_ID}")
    
    # Level 2: From User ID match
    if message.from_user and message.from_user.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append(f"User ID = {BOT_A_CHAT_ID}")
    
    # Level 3: Username match
    if message.from_user and message.from_user.username and message.from_user.username.lower() == BOT_A_USERNAME.lower():
        is_from_bot_a = True
        match_reason.append(f"Username = {BOT_A_USERNAME}")
    
    # Level 4: Forward from match
    if message.forward_from and message.forward_from.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append("Forward from Bot A")
    
    # Level 5: Reply to message from Bot A
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == BOT_A_CHAT_ID:
            is_from_bot_a = True
            match_reason.append("Replying to Bot A's message")
    
    if is_from_bot_a:
        logger.info(f"✅✅✅ MATCH: Message is from Bot A! Reasons: {match_reason}")
        await process_bot_a_message(client, message)
    else:
        logger.info(f"❌❌❌ NOT from Bot A")
    
    logger.info("=" * 80)

# ==================== PROCESS BOT A MESSAGE ====================

async def process_bot_a_message(client, message: Message):
    """Proses khusus pesan dari Bot A"""
    text = message.text or message.caption or ''
    
    logger.info("=" * 80)
    logger.info("🎯🎯🎯 PROCESSING BOT A MESSAGE 🎯🎯🎯")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"📝 Full Text: '{text}'")
    logger.info("=" * 80)
    
    # ===== CEK CAPTCHA MULTI LEVEL =====
    is_captcha = False
    captcha_code = None
    
    # Cek 1: Ada foto (PASTI captcha untuk Bot A ini)
    if message.photo:
        logger.info("📸 PHOTO DETECTED - This is definitely a captcha")
        is_captcha = True
        
        # Ambil dari caption jika ada
        if text:
            six_digit = re.findall(r'(\d{6})', text)
            if six_digit:
                captcha_code = six_digit[0]
                logger.info(f"✅ Captcha code from caption: {captcha_code}")
    
    # Cek 2: Teks mengandung angka 6 digit + kata kunci
    if not captcha_code and text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            keywords = ['captcha', 'verify', 'code', 'enter', 'verification', 'kode', 'masukkan']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = six_digit[0]
                logger.info(f"✅ Captcha code from text + keyword: {captcha_code}")
    
    # Cek 3: Baris pertama adalah 6 digit angka
    if not captcha_code and text:
        lines = text.strip().split('\n')
        if lines and lines[0].strip().isdigit() and len(lines[0].strip()) == 6:
            is_captcha = True
            captcha_code = lines[0].strip()
            logger.info(f"✅ Captcha code from first line: {captcha_code}")
    
    # Cek 4: Angka 6 digit muncul di mana pun (format captcha umum)
    if not captcha_code and text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            # Jika ada angka 6 digit, anggap captcha
            is_captcha = True
            captcha_code = six_digit[0]
            logger.info(f"✅ Captcha code from anywhere: {captcha_code}")
    
    # ===== JIKA CAPTCHA =====
    if is_captcha:
        logger.warning("🚫🚫🚫 CAPTCHA DETECTED FROM BOT A!")
        
        # Jika captcha_code belum ada (foto tanpa teks), pakai OCR
        if not captcha_code and message.photo:
            logger.info("🔍 No text code found, trying OCR...")
            captcha_code = await read_number_from_photo(message)
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅✅✅ FINAL CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # Kirim verifikasi ke Bot A
            await client.send_message(BOT_A_CHAT_ID, f"/verify {captcha_code}")
            logger.info(f"📤📤📤 Verification sent: /verify {captcha_code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            logger.info("✅ Captcha handled successfully")
            
            # Proses ulang request pending
            await retry_pending_requests()
        else:
            logger.error("❌❌❌ Failed to get captcha code")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        return
    
    # ===== BUKAN CAPTCHA - INI HASIL INFO =====
    if text:
        logger.info("📨📨📨 Processing as normal message (result)")
        
        # Ambil request dari queue
        request_id = r.lpop('pending_requests')
        
        if request_id:
            request_id = request_id.decode('utf-8')
            logger.info(f"📋 Processing request ID: {request_id}")
            
            request_data_json = r.get(request_id)
            
            if request_data_json is None:
                logger.warning(f"⚠️ Request {request_id} expired")
                return
            
            request_data = json.loads(request_data_json)
            user_id = request_data['chat_id']
            logger.info(f"👤 Forward to user: {user_id}")
            
            # Kirim ke user via Bot B
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': user_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅✅✅ SUCCESS: Forwarded to user {user_id}")
                    r.delete(request_id)
                else:
                    logger.error(f"❌ Failed to forward")
                    r.rpush('pending_requests', request_id)
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
                r.rpush('pending_requests', request_id)
    else:
        logger.warning("⚠️ Message from Bot A with no text")

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """Kirim ulang request yang pending"""
    logger.info("🔄 Retrying pending requests...")
    
    retry_count = 0
    while True:
        request_id = r.lpop('pending_requests')
        if not request_id:
            break
            
        request_id = request_id.decode('utf-8')
        request_data_json = r.get(request_id)
        
        if request_data_json is None:
            continue
        
        request_data = json.loads(request_data_json)
        cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
        
        await app.send_message(BOT_A_CHAT_ID, cmd)
        logger.info(f"🔄 Retry: {cmd}")
        
        r.setex(request_id, 300, json.dumps(request_data))
        retry_count += 1
        await asyncio.sleep(2)
    
    if retry_count > 0:
        logger.info(f"✅ Retried {retry_count} requests")

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    """Monitor queue dan kirim request ke Bot A"""
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            queue_length = r.llen('pending_requests')
            if queue_length > 0:
                logger.info(f"📊 Queue length: {queue_length}")
            
            if not bot_status['in_captcha'] and queue_length > 0:
                request_id_bytes = r.lindex('pending_requests', 0)
                
                if request_id_bytes:
                    request_id = request_id_bytes.decode('utf-8')
                    current_time = time.time()
                    
                    if request_id in sent_requests:
                        last_sent = sent_requests[request_id]
                        time_diff = current_time - last_sent
                        
                        if time_diff < 30:
                            logger.info(f"⏳ Already sent {time_diff:.1f}s ago, waiting...")
                            await asyncio.sleep(5)
                            continue
                        elif time_diff > 120:
                            logger.warning(f"⚠️ Request expired, removing")
                            r.lpop('pending_requests')
                            r.delete(request_id)
                            if request_id in sent_requests:
                                del sent_requests[request_id]
                            continue
                    
                    request_data_json = r.get(request_id)
                    if request_data_json is None:
                        r.lpop('pending_requests')
                        continue
                    
                    request_data = json.loads(request_data_json)
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    
                    try:
                        await app.send_message(BOT_A_CHAT_ID, cmd)
                        logger.info(f"📤 Sent to Bot A: {cmd}")
                        sent_requests[request_id] = current_time
                    except Exception as e:
                        logger.error(f"❌ Failed to send: {e}")
                        if "PEER_ID_INVALID" in str(e):
                            logger.warning("⏳ Bot A not ready, waiting...")
                            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"❌ Queue error: {e}")
        
        await asyncio.sleep(5)

# ==================== MAIN ====================

async def main():
    global sent_requests
    sent_requests = {}
    
    logger.info("🚀 Starting userbot...")
    
    try:
        await app.start()
        logger.info("✅ Userbot started!")
        
        me = await app.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        logger.info(f"✅ User ID: {me.id}")
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
