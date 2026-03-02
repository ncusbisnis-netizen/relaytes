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
    in_memory=True
)

bot_status = {'in_captcha': False}
sent_requests = {}

# ==================== OCR UNTUK BACA ANGKA DARI FOTO ====================

async def read_number_from_photo(photo_message):
    """
    Baca angka 6 digit dari foto captcha
    """
    try:
        logger.info("📸 Downloading captcha photo...")
        
        # Download foto
        photo_path = await photo_message.download()
        logger.info(f"✅ Photo downloaded: {photo_path}")
        
        # Buka dengan PIL
        img = Image.open(photo_path)
        
        # Convert ke grayscale (hitam putih)
        img = img.convert('L')
        
        # Tingkatkan kontras
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Threshold untuk angka putih
        threshold = 200
        img = img.point(lambda p: p > threshold and 255)
        
        # Simpan sementara
        temp_path = f"/tmp/ocr_{int(time.time())}.png"
        img.save(temp_path)
        
        # OCR dengan konfigurasi khusus angka
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        
        # Bersihkan
        os.remove(photo_path)
        os.remove(temp_path)
        
        # Ambil hanya digit
        text = re.sub(r'[^0-9]', '', text)
        logger.info(f"📝 OCR result: '{text}'")
        
        # Cari 6 digit berurutan
        match = re.search(r'(\d{6})', text)
        if match:
            code = match.group(1)
            logger.info(f"✅ Found 6-digit code: {code}")
            return code
        else:
            logger.warning("❌ No 6-digit number found in OCR result")
            
            # COBA LAGI DENGAN PREPROCESSING BERBEDA
            return await retry_ocr(photo_path)
            
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

async def retry_ocr(photo_path):
    """
    Coba lagi dengan preprocessing berbeda
    """
    try:
        logger.info("🔄 Retry OCR with different preprocessing")
        
        img = Image.open(photo_path)
        
        # Resize lebih besar
        width, height = img.size
        img = img.resize((width*2, height*2), Image.LANCZOS)
        
        # Convert ke grayscale
        img = img.convert('L')
        
        # Threshold adaptif
        import numpy as np
        import cv2
        
        img_cv = np.array(img)
        _, thresh = cv2.threshold(img_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        temp_path = f"/tmp/ocr_retry_{int(time.time())}.png"
        cv2.imwrite(temp_path, thresh)
        
        text = pytesseract.image_to_string(temp_path, config='--oem 3 --psm 8')
        
        os.remove(temp_path)
        
        text = re.sub(r'[^0-9]', '', text)
        match = re.search(r'(\d{6})', text)
        
        if match:
            return match.group(1)
        return None
    except:
        return None

# ==================== HANDLER PESAN ====================

@app.on_message()
async def handle_all_messages(client, message: Message):
    """
    Handler untuk SEMUA pesan
    """
    # AMBIL TEKS (jika ada)
    text = message.text or message.caption or ''
    
    # LOG LENGKAP
    logger.info(f"📨 INCOMING MESSAGE")
    logger.info(f"  Chat ID: {message.chat.id}")
    logger.info(f"  From User: {message.from_user.id if message.from_user else 'None'}")
    logger.info(f"  Has photo: {bool(message.photo)}")
    logger.info(f"  Text: '{text[:100]}'")
    
    # CEK APAKAH DARI BOT A
    is_from_bot_a = False
    
    if message.chat.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
    
    if message.from_user and message.from_user.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
    
    if not is_from_bot_a:
        return
    
    # ===== INI PESAN DARI BOT A =====
    logger.info("🔥 PROCESSING MESSAGE FROM BOT A")
    
    # ===== CEK CAPTCHA (FOTO) =====
    if message.photo:
        logger.warning("🚫 PHOTO CAPTCHA DETECTED!")
        bot_status['in_captcha'] = True
        
        # BACA ANGKA DARI FOTO
        code = await read_number_from_photo(message)
        
        if code:
            logger.info(f"✅ CAPTCHA CODE: {code}")
            
            # KIRIM VERIFIKASI
            await client.send_message(BOT_A_CHAT_ID, f"/verify {code}")
            logger.info(f"📤 Verification sent: /verify {code}")
            
            await asyncio.sleep(3)
            bot_status['in_captcha'] = False
            
            # PROSES ULANG REQUEST
            await retry_pending_requests()
        else:
            logger.error("❌ Failed to read captcha code")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        return
    
    # ===== BUKAN FOTO - INI HASIL INFO =====
    logger.info("📨 Processing as normal message (result)")
    
    # AMBIL REQUEST DARI QUEUE
    request_id = r.lpop('pending_requests')
    
    if request_id:
        request_id = request_id.decode('utf-8')
        request_data_json = r.get(request_id)
        
        if request_data_json is None:
            logger.warning(f"⚠️ Request expired")
            return
        
        request_data = json.loads(request_data_json)
        user_id = request_data['chat_id']
        
        # KIRIM KE USER VIA BOT B
        url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Forwarded to user {user_id}")
                r.delete(request_id)
            else:
                logger.error(f"❌ Failed to forward")
                r.rpush('pending_requests', request_id)
        except Exception as e:
            logger.error(f"❌ Forward error: {e}")
            r.rpush('pending_requests', request_id)

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """Kirim ulang request setelah captcha selesai"""
    logger.info("🔄 Retrying pending requests...")
    
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
        await asyncio.sleep(2)

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    """Monitor queue dan kirim request ke Bot A"""
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
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    
                    await app.send_message(BOT_A_CHAT_ID, cmd)
                    logger.info(f"📤 Request sent: {cmd}")
                    
                    r.setex(request_id, 300, json.dumps(request_data))
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(5)

# ==================== MAIN ====================

async def main():
    logger.info("🚀 Starting userbot...")
    
    try:
        await app.start()
        logger.info("✅ Userbot started!")
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
