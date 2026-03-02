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
import pytesseract
from PIL import Image, ImageEnhance
import cv2
import numpy as np

# Set path Tesseract untuk Heroku
pytesseract.pytesseract.tesseract_cmd = '/app/.apt/usr/bin/tesseract'
os.environ['TESSDATA_PREFIX'] = '/app/.apt/usr/share/tesseract-ocr/5/tessdata/'

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

# Telethon Client
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

bot_status = {'in_captcha': False}
sent_requests = {}

# ==================== OCR FUNCTION (IMPROVED) ====================

async def read_number_from_photo(message):
    """Baca angka 6 digit dari foto captcha dengan preprocessing optimal"""
    photo_path = None
    temp_path = None
    
    try:
        logger.info("📸 OCR: Downloading captcha photo...")
        photo_path = await message.download_media()
        logger.info(f"✅ Photo downloaded: {photo_path}")
        
        # ===== PREPROCESSING 1: PIL Basic =====
        img = Image.open(photo_path)
        
        # Convert ke grayscale
        img = img.convert('L')
        
        # Tingkatkan kontras (agresif)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(3.0)
        
        # Threshold sederhana
        img = img.point(lambda p: p > 180 and 255)
        
        temp_path = f"/tmp/ocr_pil_{int(time.time())}.png"
        img.save(temp_path)
        
        # OCR attempt 1
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        text = re.sub(r'[^0-9]', '', text)
        
        if re.search(r'\d{6}', text):
            code = re.search(r'\d{6}', text).group()
            logger.info(f"✅ OCR success (PIL): {code}")
            return code
        
        # ===== PREPROCESSING 2: OpenCV Advanced =====
        logger.info("🔄 Trying OpenCV preprocessing...")
        
        img_cv = cv2.imread(photo_path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Adaptive threshold
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        # Dilasi untuk mempertebal angka
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        # Resize 2x
        resized = cv2.resize(dilated, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        temp_path2 = f"/tmp/ocr_cv_{int(time.time())}.png"
        cv2.imwrite(temp_path2, resized)
        
        # OCR attempt 2
        text2 = pytesseract.image_to_string(temp_path2, config=custom_config)
        text2 = re.sub(r'[^0-9]', '', text2)
        
        if re.search(r'\d{6}', text2):
            code = re.search(r'\d{6}', text2).group()
            logger.info(f"✅ OCR success (OpenCV): {code}")
            return code
        
        # ===== PREPROCESSING 3: Inverted colors =====
        inverted = cv2.bitwise_not(resized)
        temp_path3 = f"/tmp/ocr_inv_{int(time.time())}.png"
        cv2.imwrite(temp_path3, inverted)
        
        text3 = pytesseract.image_to_string(temp_path3, config=custom_config)
        text3 = re.sub(r'[^0-9]', '', text3)
        
        if re.search(r'\d{6}', text3):
            code = re.search(r'\d{6}', text3).group()
            logger.info(f"✅ OCR success (Inverted): {code}")
            return code
        
        logger.warning("❌ All OCR attempts failed")
        return None
        
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None
    finally:
        # Bersihkan semua file temporary
        for path in [photo_path, temp_path, temp_path2, temp_path3]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

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
    
    # Ambil teks
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
    
    # CEK APAKAH DARI BOT A
    if chat_id != BOT_A_CHAT_ID and sender_id != BOT_A_CHAT_ID:
        logger.info("❌ Bukan dari Bot A")
        logger.info("=" * 80)
        return
    
    logger.info("🎯🎯🎯 PESAN DARI BOT A DITERIMA!")
    
    # ===== CEK CAPTCHA =====
    is_captcha = False
    captcha_code = None
    
    # Cek 1: Ada foto (kemungkinan besar captcha)
    if message.photo:
        logger.info("📸 PHOTO DETECTED - This is a captcha")
        is_captcha = True
        
        # Cek apakah ada angka di teks/caption
        if text:
            six_digit = re.findall(r'(\d{6})', text)
            if six_digit:
                captcha_code = six_digit[0]
                logger.info(f"✅ Found code in caption: {captcha_code}")
    
    # Cek 2: Teks mengandung angka 6 digit + kata kunci
    if not captcha_code and text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            keywords = ['captcha', 'verify', 'code', 'enter', 'kode']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = six_digit[0]
                logger.info(f"✅ Found code in text: {captcha_code}")
    
    # Cek 3: Baris pertama 6 digit
    if not captcha_code and text:
        lines = text.strip().split('\n')
        if lines and lines[0].strip().isdigit() and len(lines[0].strip()) == 6:
            is_captcha = True
            captcha_code = lines[0].strip()
            logger.info(f"✅ Found code in first line: {captcha_code}")
    
    # ===== JIKA CAPTCHA =====
    if is_captcha:
        logger.warning("🚫 CAPTCHA DETECTED!")
        
        # Jika captcha_code belum ada (foto tanpa teks), pakai OCR
        if not captcha_code and message.photo:
            logger.info("🔍 No text code found, trying OCR...")
            captcha_code = await read_number_from_photo(message)
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # Kirim verifikasi ke Bot A
            await client.send_message(BOT_A_CHAT_ID, f"/verify {captcha_code}")
            logger.info(f"📤📤📤 Verification sent: /verify {captcha_code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            logger.info("✅ Captcha handled")
            
            # Proses ulang request pending
            await retry_pending_requests()
        else:
            logger.error("❌❌❌ Gagal mendapatkan captcha code")
            logger.info("⏳ Menunggu 60 detik sebelum coba lagi...")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        logger.info("=" * 80)
        return
    
    # ===== BUKAN CAPTCHA - INI HASIL INFO =====
    # HANYA sampai di sini jika bukan captcha
    logger.info("📨📨📨 Memproses sebagai hasil info (BUKAN captcha)")
    
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
                            logger.warning(f"⚠️ Request expired (>2 menit), removing")
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
        await client.start()
        logger.info("✅ Telethon client started!")
        
        me = await client.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        
        client.add_event_handler(message_handler)
        client.add_event_handler(message_edit_handler)
        logger.info("✅ Event handlers registered")
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
