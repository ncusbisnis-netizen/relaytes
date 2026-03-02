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
import pytesseract
from PIL import Image
import cv2
import numpy as np

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
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))

# Validasi environment variables
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, BOT_A_CHAT_ID, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    logger.error(f"API_ID: {'✅' if API_ID else '❌'}")
    logger.error(f"API_HASH: {'✅' if API_HASH else '❌'}")
    logger.error(f"SESSION_STRING: {'✅' if SESSION_STRING else '❌'}")
    logger.error(f"BOT_B_TOKEN: {'✅' if BOT_B_TOKEN else '❌'}")
    logger.error(f"BOT_A_CHAT_ID: {'✅' if BOT_A_CHAT_ID else '❌'}")
    logger.error(f"REDIS_URL: {'✅' if REDIS_URL else '❌'}")
    exit(1)

# Redis connection
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

# Pyrogram Client dengan session string
app = Client(
    name="relay_bot",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

bot_status = {'in_captcha': False}

# ==================== FUNGSI OCR UNTUK CAPTCHA ====================

async def solve_captcha_simple(message):
    """
    OCR sederhana khusus angka 6 digit dari gambar
    """
    try:
        logger.info("📸 OCR: Downloading captcha image...")
        
        # Download foto
        photo_path = await message.download()
        logger.info(f"✅ Image downloaded: {photo_path}")
        
        # Buka dengan PIL
        img = Image.open(photo_path)
        
        # Convert ke grayscale
        img = img.convert('L')
        
        # Threshold sederhana
        threshold = 200
        img = img.point(lambda p: p > threshold and 255)
        
        # Simpan sementara
        temp_path = f"/tmp/captcha_{int(time.time())}.png"
        img.save(temp_path)
        
        # OCR dengan pytesseract (khusus angka)
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        
        # Bersihkan file
        os.remove(photo_path)
        os.remove(temp_path)
        
        # Ambil 6 digit
        text = re.sub(r'[^0-9]', '', text)
        match = re.search(r'(\d{6})', text)
        
        if match:
            code = match.group(1)
            logger.info(f"✅ OCR BERHASIL: {code}")
            return code
        else:
            logger.warning(f"❌ OCR GAGAL: {text}")
            return None
        
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

# ==================== DETEKSI CAPTCHA ====================

def detect_captcha(message):
    """
    Deteksi apakah pesan adalah captcha
    """
    text = message.text or message.caption or ''
    
    # Cek angka 6 digit
    six_digit = re.findall(r'(\d{6})', text)
    
    # Kondisi captcha: ada foto ATAU ada angka 6 digit dengan kata kunci
    if message.photo:
        logger.info("📸 Photo detected - potential captcha")
        return True, six_digit[0] if six_digit else None
    
    if six_digit and ('captcha' in text.lower() or 'verify' in text.lower() or 'code' in text.lower()):
        logger.info(f"🔢 Text captcha detected: {six_digit[0]}")
        return True, six_digit[0]
    
    return False, None

# ==================== HANDLER UTAMA PESAN DARI BOT A ====================

@app.on_message(filters.chat(BOT_A_CHAT_ID))
async def handle_bot_reply(client, message: Message):
    """
    Handler untuk semua pesan dari Bot A
    """
    text = message.text or message.caption or ''
    
    logger.info(f"🔥 Message from Bot A")
    logger.info(f"📸 Has photo: {bool(message.photo)}")
    logger.info(f"📝 Text: {text[:100]}")
    
    # ===== CEK CAPTCHA =====
    is_captcha, captcha_code = detect_captcha(message)
    
    if is_captcha:
        logger.warning("🚫 CAPTCHA DETECTED!")
        bot_status['in_captcha'] = True
        
        # Dapatkan kode captcha
        code = None
        
        if captcha_code:
            # Dapat dari teks
            code = captcha_code
            logger.info(f"✅ Code from text: {code}")
        elif message.photo:
            # OCR dari gambar
            code = await solve_captcha_simple(message)
            logger.info(f"✅ Code from OCR: {code}" if code else "❌ OCR failed")
        
        if code:
            # Kirim verifikasi
            await client.send_message(BOT_A_CHAT_ID, f"/verify {code}")
            logger.info(f"📤 Verification sent: /verify {code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            logger.info("✅ Captcha handled, resuming normal operation")
            
            # Proses ulang request yang pending
            await retry_pending_requests()
        else:
            logger.error("❌ Failed to get captcha code")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        return
    
    # ===== BUKAN CAPTCHA - HARUSNYA INI HASIL INFO =====
    logger.info("📨 Processing as normal message (result)")
    
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
        logger.info(f"👤 Forward to user: {request_data['chat_id']}")
        
        # Kirim ke user via Bot B
        url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
        data = {
            'chat_id': request_data['chat_id'],
            'text': text,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ SUCCESS: Forwarded to user {request_data['chat_id']}")
            else:
                logger.error(f"❌ Failed to forward: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                # Kembalikan ke queue
                r.rpush('pending_requests', request_id)
                
        except Exception as e:
            logger.error(f"❌ Forward error: {e}")
            r.rpush('pending_requests', request_id)
    else:
        logger.warning("⚠️ No pending requests in queue")

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """
    Kirim ulang request yang pending setelah captcha selesai
    """
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
        
        # Kirim ulang ke Bot A
        cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
        await app.send_message(BOT_A_CHAT_ID, cmd)
        logger.info(f"🔄 Retry: {cmd}")
        
        # Simpan kembali
        r.setex(request_id, 300, json.dumps(request_data))
        
        retry_count += 1
        await asyncio.sleep(2)
    
    if retry_count > 0:
        logger.info(f"✅ Retried {retry_count} requests")

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    """
    Monitor queue dan kirim request ke Bot A
    """
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            if not bot_status['in_captcha']:
                request_id = r.lpop('pending_requests')
                
                if request_id:
                    request_id = request_id.decode('utf-8')
                    request_data_json = r.get(request_id)
                    
                    if request_data_json is None:
                        continue
                    
                    request_data = json.loads(request_data_json)
                    
                    # Kirim ke Bot A
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    await app.send_message(BOT_A_CHAT_ID, cmd)
                    logger.info(f"📤 Request sent: {cmd}")
                    
                    # Simpan kembali
                    r.setex(request_id, 300, json.dumps(request_data))
            
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(3)

# ==================== MAIN FUNCTION ====================

async def main():
    """
    Fungsi utama
    """
    logger.info("🚀 Starting userbot...")
    
    try:
        # Start Pyrogram client
        await app.start()
        logger.info("✅ Userbot started!")
        
        # LANGSUNG JALANKAN QUEUE PROCESSOR
        # TIDAK PERLU KIRIM /start KE BOT A
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    asyncio.run(main())
