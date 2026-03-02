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

# Fungsi OCR untuk captcha
async def solve_captcha(photo_message: Message):
    """
    Mengekstrak 6 digit angka dari gambar captcha
    """
    try:
        logger.info("📸 Downloading captcha image...")
        
        # Download foto ke file temporary
        photo_path = await photo_message.download()
        logger.info(f"✅ Image downloaded: {photo_path}")
        
        # Baca dengan OpenCV
        img = cv2.imread(photo_path)
        
        if img is None:
            logger.error("❌ Failed to read image with OpenCV")
            return None
        
        # PREPROCESSING untuk angka putih di background gelap
        # 1. Convert ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Thresholding (angka putih, background gelap)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # 3. Dilasi untuk mempertebal angka
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        # 4. Simpan hasil preprocessing
        processed_path = f"/tmp/processed_{int(time.time())}.png"
        cv2.imwrite(processed_path, dilated)
        
        # 5. OCR dengan Tesseract (khusus angka)
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(processed_path, config=custom_config)
        
        # Hapus file temporary
        os.remove(photo_path)
        os.remove(processed_path)
        
        # 6. Bersihkan hasil (ambil hanya digit)
        text = re.sub(r'[^0-9]', '', text.strip())
        logger.info(f"OCR raw text: {text}")
        
        # 7. Cari 6 digit berurutan
        match = re.search(r'(\d{6})', text)
        
        if match:
            code = match.group(1)
            logger.info(f"✅ OCR BERHASIL: {code}")
            return code
        else:
            logger.warning(f"❌ OCR GAGAL: {text}")
            
            # Fallback: coba preprocessing berbeda
            return await solve_captcha_fallback(img)
            
    except Exception as e:
        logger.error(f"❌ Error OCR: {e}")
        return None

async def solve_captcha_fallback(img):
    """
    Fallback dengan preprocessing berbeda
    """
    try:
        logger.info("🔄 Mencoba metode OCR alternatif...")
        
        # Metode alternatif
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 11, 2)
        
        # Resize untuk memperbesar
        scaled = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        temp_path = f"/tmp/captcha_fallback_{int(time.time())}.png"
        cv2.imwrite(temp_path, scaled)
        
        text = pytesseract.image_to_string(temp_path, config='--oem 3 --psm 8')
        
        os.remove(temp_path)
        
        text = re.sub(r'[^0-9]', '', text.strip())
        match = re.search(r'(\d{6})', text)
        
        if match:
            return match.group(1)
        return None
    except Exception as e:
        logger.error(f"❌ Fallback OCR error: {e}")
        return None

# Kirim notifikasi ke admin via Bot B
def notify_admin(message):
    if os.environ.get('ADMIN_CHAT_ID'):
        try:
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': int(os.environ.get('ADMIN_CHAT_ID')),
                'text': f"🤖 Relay Bot:\n{message}"
            }
            requests.post(url, json=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

# Handler untuk pesan dari Bot A
@app.on_message(filters.chat(BOT_A_CHAT_ID))
async def handle_bot_reply(client, message: Message):
    text = message.text or message.caption or ''
    
    logger.info(f"📩 From Bot A: {text[:100]}")
    
    # CEK CAPTCHA (foto + kata kunci)
    if message.photo and ('captcha' in text.lower() or 'verify' in text.lower()):
        logger.warning("🚫 CAPTCHA DETECTED!")
        bot_status['in_captcha'] = True
        
        notify_admin("🚫 Captcha detected, solving...")
        
        # SOLVE CAPTCHA DENGAN OCR
        code = await solve_captcha(message)
        
        if code and len(code) == 6:
            logger.info(f"✅ Captcha solved: {code}")
            
            # Kirim verifikasi ke Bot A
            await client.send_message(BOT_A_CHAT_ID, f"/verify {code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            notify_admin(f"✅ Captcha solved: {code}")
            
            # Proses ulang request yang pending
            await retry_pending_requests()
        else:
            logger.error("❌ Gagal solve captcha")
            notify_admin("❌ OCR failed, waiting 5 minutes...")
            await asyncio.sleep(300)
            bot_status['in_captcha'] = False
        
        return
    
    # FORWARD KE USER (hasil normal)
    if not bot_status['in_captcha'] and not message.photo:
        try:
            # Ambil request dari queue
            request_id = r.lpop('pending_requests')
            if request_id:
                request_id = request_id.decode('utf-8')
                request_data_json = r.get(request_id)
                
                # CEK APAKAH DATA MASIH ADA (TIDAK EXPIRED)
                if request_data_json is None:
                    logger.warning(f"⚠️ Request {request_id} sudah expired, dilewati")
                    return
                
                request_data = json.loads(request_data_json)
                
                # Kirim ke user via Bot B
                url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
                data = {
                    'chat_id': request_data['chat_id'],
                    'text': text,
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(url, json=data, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅ Forwarded to user {request_data['chat_id']}")
                else:
                    logger.error(f"❌ Failed to forward: {response.text}")
                    # Kembalikan ke queue
                    r.rpush('pending_requests', request_id)
            else:
                logger.debug("No pending requests")
        except Exception as e:
            logger.error(f"❌ Forward error: {e}")

async def retry_pending_requests():
    """Kirim ulang request yang pending setelah captcha selesai"""
    logger.info("🔄 Processing pending requests...")
    while True:
        request_id = r.lpop('pending_requests')
        if not request_id:
            break
            
        request_id = request_id.decode('utf-8')
        request_data_json = r.get(request_id)
        
        # CEK APAKAH DATA MASIH ADA
        if request_data_json is None:
            logger.warning(f"⚠️ Request {request_id} sudah expired, dilewati")
            continue
        
        request_data = json.loads(request_data_json)
        
        cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
        await app.send_message(BOT_A_CHAT_ID, cmd)
        logger.info(f"🔄 Retry: {cmd}")
        
        # Simpan kembali untuk nanti diambil responsenya
        r.setex(request_id, 300, json.dumps(request_data))
        
        await asyncio.sleep(2)

# Handler untuk /start (untuk test)
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    await message.reply("✅ Relay bot aktif!")

# Queue processor
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
                    
                    # CEK APAKAH DATA MASIH ADA (TIDAK EXPIRED)
                    if request_data_json is None:
                        logger.warning(f"⚠️ Request {request_id} sudah expired, dilewati")
                        continue
                    
                    request_data = json.loads(request_data_json)
                    
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    await app.send_message(BOT_A_CHAT_ID, cmd)
                    logger.info(f"📤 Request sent: {cmd}")
                    
                    # Simpan kembali untuk nanti diambil responsenya
                    r.setex(request_id, 300, json.dumps(request_data))
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(3)

async def main():
    """Main function"""
    logger.info("🚀 Starting userbot...")
    
    try:
        await app.start()
        logger.info("✅ Userbot started!")
        
        # Test connection ke Bot A
        try:
            await app.send_message(BOT_A_CHAT_ID, "/start")
            logger.info("✅ Connected to Bot A")
        except Exception as e:
            logger.warning(f"⚠️ Could not send /start to Bot A: {e}")
        
        # Kirim notifikasi admin
        notify_admin("✅ Relay bot started!")
        
        # Jalankan queue processor
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        notify_admin(f"❌ Relay bot failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
