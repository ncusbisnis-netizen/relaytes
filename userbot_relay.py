from telethon import TelegramClient, events
from telethon.sessions import StringSession
import redis
import asyncio
import os
import time
import re
import logging
import json
import requests
from PIL import Image, ImageEnhance
import pytesseract
import io

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

# Set Tesseract path untuk Heroku
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/5/tessdata/'

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

# Telethon Client dengan StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

bot_status = {'in_captcha': False}
sent_requests = {}

# ==================== OCR FUNCTION (FALLBACK) ====================

async def read_number_from_photo(message):
    """Baca angka 6 digit dari foto captcha - FALLBACK jika tidak ada teks"""
    try:
        logger.info("📸 OCR Fallback: Downloading captcha photo...")
        
        # Download foto
        photo_path = await message.download_media()
        logger.info(f"✅ Photo downloaded: {photo_path}")
        
        # Buka dengan PIL
        img = Image.open(photo_path)
        
        # Convert ke grayscale
        img = img.convert('L')
        
        # Tingkatkan kontras
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Threshold
        img = img.point(lambda p: p > 200 and 255)
        
        # Simpan sementara
        temp_path = f"/tmp/ocr_{int(time.time())}.png"
        img.save(temp_path)
        
        # OCR dengan Tesseract
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
            logger.info(f"✅ OCR success: {code}")
            return code
        logger.warning("❌ OCR failed: no 6-digit number found")
        return None
        
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """Kirim ulang request yang pending setelah captcha selesai"""
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
        
        await client.send_message(BOT_A_CHAT_ID, cmd)
        logger.info(f"🔄 Retry: {cmd}")
        
        r.setex(request_id, 300, json.dumps(request_data))
        retry_count += 1
        await asyncio.sleep(2)
    
    if retry_count > 0:
        logger.info(f"✅ Retried {retry_count} requests")

# ==================== TELEGRAM EVENT HANDLER ====================

@events.register(events.NewMessage)
async def message_handler(event):
    """
    Handler untuk semua pesan baru
    """
    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    
    # Ambil teks dari mana pun
    text = message.text or message.message or ''
    
    # LOG LENGKAP
    logger.info("=" * 80)
    logger.info("🔥🔥🔥 TELETHON MESSAGE HANDLER 🔥🔥🔥")
    logger.info(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📌 Message ID: {message.id}")
    logger.info(f"💬 Chat ID: {chat_id}")
    logger.info(f"👤 Sender ID: {sender_id}")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"📝 Text: '{text[:200]}'")
    
    # ===== CEK APAKAH DARI BOT A =====
    is_from_bot_a = False
    
    if chat_id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        logger.info("✅ MATCH: Chat ID = Bot A")
    
    if sender_id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        logger.info("✅ MATCH: Sender ID = Bot A")
    
    if not is_from_bot_a:
        logger.info("❌ Bukan dari Bot A")
        logger.info("=" * 80)
        return
    
    # ===== INI PESAN DARI BOT A =====
    logger.info("🎯🎯🎯 PESAN DARI BOT A DITERIMA!")
    
    # ===== CEK CAPTCHA - PRIORITAS AMBIL DARI TEKS =====
    is_captcha = False
    captcha_code = None
    
    # CEK 1: Cari angka 6 digit di TEKS (caption atau message)
    if text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            # Ambil angka 6 digit pertama
            captcha_code = six_digit[0]
            
            # Cek apakah ini captcha (ada foto atau kata kunci)
            if message.photo:
                is_captcha = True
                logger.info(f"📸 PHOTO + TEXT CAPTCHA: {captcha_code}")
            else:
                # Cek kata kunci
                keywords = ['captcha', 'verify', 'code', 'enter', 'verification', 'kode']
                if any(kw in text.lower() for kw in keywords):
                    is_captcha = True
                    logger.info(f"✅ TEXT CAPTCHA with keyword: {captcha_code}")
    
    # CEK 2: Baris pertama 6 digit (format umum captcha)
    if not captcha_code and text:
        lines = text.strip().split('\n')
        if lines and lines[0].strip().isdigit() and len(lines[0].strip()) == 6:
            captcha_code = lines[0].strip()
            is_captcha = True
            logger.info(f"✅ CAPTCHA from first line: {captcha_code}")
    
    # CEK 3: Foto tanpa teks (pake OCR)
    if not captcha_code and message.photo:
        logger.info("📸 PHOTO WITHOUT TEXT - trying OCR fallback")
        is_captcha = True
        captcha_code = await read_number_from_photo(message)
    
    # ===== JIKA CAPTCHA, VERIFIKASI =====
    if is_captcha and captcha_code and len(captcha_code) == 6:
        logger.warning(f"🚫🚫🚫 CAPTCHA CODE: {captcha_code}")
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
        
        logger.info("=" * 80)
        return
    
    # ===== BUKAN CAPTCHA - HASIL INFO =====
    if text:
        logger.info("📨📨📨 Hasil info dari Bot A")
        
        # Ambil request dari queue
        request_id = r.lpop('pending_requests')
        
        if request_id:
            request_id = request_id.decode('utf-8')
            logger.info(f"📋 Request ID: {request_id}")
            
            request_data_json = r.get(request_id)
            
            if request_data_json is None:
                logger.warning(f"⚠️ Request expired")
                logger.info("=" * 80)
                return
            
            request_data = json.loads(request_data_json)
            user_id = request_data['chat_id']
            
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
                    logger.info(f"✅✅✅ Terkirim ke user {user_id}")
                    r.delete(request_id)
                else:
                    logger.error(f"❌ Gagal forward: {response.status_code}")
                    r.rpush('pending_requests', request_id)
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
                r.rpush('pending_requests', request_id)
        else:
            logger.warning("⚠️ Tidak ada request pending")
    
    logger.info("=" * 80)

@events.register(events.MessageEdited)
async def message_edit_handler(event):
    """Handler untuk pesan yang diedit"""
    logger.info(f"✏️ Message edited in chat {event.chat_id}")

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
                            logger.warning(f"⚠️ Request expired (>2 menit), removing from queue")
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
                        await client.send_message(BOT_A_CHAT_ID, cmd)
                        logger.info(f"📤 Sent to Bot A: {cmd}")
                        sent_requests[request_id] = current_time
                    except Exception as e:
                        logger.error(f"❌ Failed to send to Bot A: {e}")
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(5)

# ==================== MAIN ====================

async def main():
    global sent_requests
    sent_requests = {}
    
    logger.info("🚀 Starting Telethon userbot...")
    
    try:
        # Start client
        await client.start()
        logger.info("✅ Telethon client started!")
        
        # Dapatkan info user
        me = await client.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        logger.info(f"✅ User ID: {me.id}")
        
        # Daftarkan event handlers
        client.add_event_handler(message_handler)
        client.add_event_handler(message_edit_handler)
        logger.info("✅ Event handlers registered")
        
        # Jalankan queue processor
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
