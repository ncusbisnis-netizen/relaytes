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
from PIL import Image, ImageEnhance
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
sent_requests = {}  # Untuk tracking pengiriman

# ==================== FUNGSI OCR UNTUK CAPTCHA ====================

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
        
        # Bersihkan file
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
            return None
            
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

# ==================== HANDLER SEMUA PESAN ====================

@app.on_message()
async def handle_all_messages(client, message: Message):
    """
    Handler untuk SEMUA pesan - dengan logging super lengkap
    """
    # AMBIL TEKS DARI MANAPUN
    text = ""
    if message.text:
        text = message.text
        text_source = "message.text"
    elif message.caption:
        text = message.caption
        text_source = "message.caption"
    else:
        text = ""
        text_source = "none"
    
    # LOG LENGKAP UNTUK SEMUA PESAN YANG MASUK
    logger.info("=" * 60)
    logger.info("📥 RAW MESSAGE RECEIVED - DETAIL LENGKAP")
    logger.info(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"💬 Message ID: {message.id}")
    logger.info(f"👤 Chat ID: {message.chat.id}")
    logger.info(f"👤 From User ID: {message.from_user.id if message.from_user else 'None'}")
    logger.info(f"👤 From Username: @{message.from_user.username if message.from_user and message.from_user.username else 'None'}")
    logger.info(f"👤 From First Name: {message.from_user.first_name if message.from_user else 'None'}")
    logger.info(f"📸 Has photo: {bool(message.photo)}")
    logger.info(f"🎥 Has video: {bool(message.video)}")
    logger.info(f"📄 Has document: {bool(message.document)}")
    logger.info(f"🔊 Has audio: {bool(message.audio)}")
    logger.info(f"📊 Has media group: {bool(message.media_group_id)}")
    logger.info(f"📝 Text source: {text_source}")
    logger.info(f"📝 Text length: {len(text)}")
    logger.info(f"📝 Text content: '{text}'")
    logger.info(f"📝 Text preview: '{text[:200]}'")
    
    if message.photo:
        logger.info(f"🖼️ Photo info: {message.photo}")
    
    if message.reply_markup:
        logger.info(f"🔘 Has reply markup: {message.reply_markup}")
    
    # CEK APAKAH DARI BOT A (MULTIPLE CHECK)
    is_from_bot_a = False
    match_reason = []
    
    # Check 1: Chat ID
    if message.chat.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append("chat_id")
    
    # Check 2: From User ID
    if message.from_user and message.from_user.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append("user_id")
    
    # Check 3: Username
    if message.from_user and message.from_user.username and message.from_user.username.lower() == 'bengkelmlbb_bot':
        is_from_bot_a = True
        match_reason.append("username")
    
    # Check 4: Forward from
    if message.forward_from and message.forward_from.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append("forward_from")
    
    # Check 5: Forward from chat
    if message.forward_from_chat and message.forward_from_chat.id == BOT_A_CHAT_ID:
        is_from_bot_a = True
        match_reason.append("forward_from_chat")
    
    if is_from_bot_a:
        logger.info(f"✅✅✅ MATCH: Message is from Bot A! Reason: {match_reason}")
    else:
        logger.info(f"❌❌❌ NOT MATCH: Message is NOT from Bot A")
        logger.info("=" * 60)
        return
    
    # ===== INI PESAN DARI BOT A =====
    logger.info("🔥🔥🔥 PROCESSING MESSAGE FROM BOT A")
    
    # ===== CEK APAKAH INI CAPTCHA =====
    is_captcha = False
    captcha_code = None
    
    # Kondisi 1: Ada foto (kemungkinan besar captcha)
    if message.photo:
        logger.info("📸 PHOTO DETECTED - kemungkinan captcha")
        is_captcha = True
        
        # Coba ambil dari caption dulu
        if text:
            six_digit = re.findall(r'(\d{6})', text)
            if six_digit:
                captcha_code = six_digit[0]
                logger.info(f"✅ Found 6-digit in caption: {captcha_code}")
    
    # Kondisi 2: Tidak ada foto tapi ada teks dengan angka 6 digit
    elif text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            # Cek apakah ada kata kunci captcha
            keywords = ['captcha', 'verify', 'code', 'enter', 'verification', 'kode']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = six_digit[0]
                logger.info(f"✅ Text captcha detected: {captcha_code}")
    
    # ===== JIKA CAPTCHA, PROSES =====
    if is_captcha:
        logger.warning(f"🚫🚫🚫 CAPTCHA DETECTED!")
        
        # Jika captcha_code belum ada (foto tanpa caption), pakai OCR
        if not captcha_code and message.photo:
            logger.info("🔍 No code in caption, trying OCR...")
            captcha_code = await read_number_from_photo(message)
        
        if captcha_code:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # Kirim verifikasi ke Bot A
            await client.send_message(BOT_A_CHAT_ID, f"/verify {captcha_code}")
            logger.info(f"📤📤📤 Verification sent: /verify {captcha_code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            logger.info("✅ Captcha handled, resuming normal operation")
            
            # Proses ulang request yang pending
            await retry_pending_requests()
        else:
            logger.error("❌❌❌ Failed to get captcha code")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        logger.info("=" * 60)
        return
    
    # ===== BUKAN CAPTCHA - INI HASIL INFO =====
    logger.info("📨📨📨 Processing as normal message (result)")
    
    # AMBIL REQUEST DARI QUEUE (FIFO)
    request_id = r.lpop('pending_requests')
    
    if request_id:
        request_id = request_id.decode('utf-8')
        logger.info(f"📋 Processing request ID: {request_id}")
        
        request_data_json = r.get(request_id)
        
        if request_data_json is None:
            logger.warning(f"⚠️ Request {request_id} expired or not found")
            
            # TAMPILKAN SEMUA REQUEST DI REDIS
            all_keys = r.keys('req:*')
            logger.info(f"🔑 All Redis keys: {all_keys}")
            logger.info("=" * 60)
            return
        
        request_data = json.loads(request_data_json)
        user_id = request_data['chat_id']
        logger.info(f"👤 Forward to user: {user_id}")
        logger.info(f"💬 Original command: {request_data['command']} {' '.join(request_data['args'])}")
        
        # ===== KIRIM KE USER VIA BOT B =====
        url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        logger.info(f"📤 Sending to Bot B API...")
        
        try:
            response = requests.post(url, json=data, timeout=10)
            logger.info(f"📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"✅✅✅ SUCCESS: Forwarded to user {user_id}")
                
                # HAPUS REQUEST DARI REDIS DAN TRACKING
                r.delete(request_id)
                if request_id in sent_requests:
                    del sent_requests[request_id]
                
            else:
                logger.error(f"❌ Failed to forward: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                
                # Kembalikan ke queue kalau gagal
                r.rpush('pending_requests', request_id)
                logger.info(f"🔄 Request {request_id} returned to queue")
                
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout saat mengirim ke Bot B")
            r.rpush('pending_requests', request_id)
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection error: {e}")
            r.rpush('pending_requests', request_id)
            
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            r.rpush('pending_requests', request_id)
    else:
        logger.warning("⚠️ No pending requests in queue")
        
        # TAMPILKAN QUEUE UNTUK DEBUG
        queue_content = r.lrange('pending_requests', 0, -1)
        logger.info(f"📋 Current queue: {queue_content}")
    
    logger.info("=" * 60)

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
            logger.warning(f"⚠️ Request {request_id} expired")
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
            # Cek panjang queue
            queue_length = r.llen('pending_requests')
            if queue_length > 0:
                logger.info(f"📊 Queue length: {queue_length}")
            
            if not bot_status['in_captcha'] and queue_length > 0:
                # Ambil request pertama tanpa menghapus
                request_id_bytes = r.lindex('pending_requests', 0)
                
                if request_id_bytes:
                    request_id = request_id_bytes.decode('utf-8')
                    
                    # CEK APAKAH REQUEST INI SUDAH PERNAH DIKIRIM
                    current_time = time.time()
                    
                    if request_id in sent_requests:
                        last_sent = sent_requests[request_id]
                        time_diff = current_time - last_sent
                        
                        # Jika sudah dikirim kurang dari 30 detik yang lalu, SKIP
                        if time_diff < 30:
                            logger.info(f"⏳ Request {request_id} already sent {time_diff:.1f}s ago, waiting...")
                            await asyncio.sleep(5)
                            continue
                        elif time_diff > 120:  # Lebih dari 2 menit, anggap expired
                            logger.warning(f"⚠️ Request {request_id} expired (>2 minutes), removing from queue")
                            # Hapus dari queue
                            r.lpop('pending_requests')
                            r.delete(request_id)
                            if request_id in sent_requests:
                                del sent_requests[request_id]
                            continue
                    
                    # Ambil data request
                    request_data_json = r.get(request_id)
                    
                    if request_data_json is None:
                        logger.warning(f"⚠️ Request {request_id} data not found, removing from queue")
                        r.lpop('pending_requests')
                        continue
                    
                    request_data = json.loads(request_data_json)
                    
                    # Kirim ke Bot A
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    logger.info(f"📤 Sending to Bot A: {cmd}")
                    
                    try:
                        await app.send_message(BOT_A_CHAT_ID, cmd)
                        logger.info(f"✅ Sent to Bot A: {cmd}")
                        
                        # Catat waktu pengiriman
                        sent_requests[request_id] = current_time
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to send to Bot A: {e}")
                        
                        # Kalau error, tunggu sebentar
                        if "PEER_ID_INVALID" in str(e):
                            logger.warning("⏳ Bot A not ready, waiting 30 seconds...")
                            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(5)

# ==================== MAIN FUNCTION ====================

async def main():
    """
    Fungsi utama
    """
    global sent_requests
    sent_requests = {}  # Reset setiap restart
    
    logger.info("🚀 Starting userbot...")
    
    try:
        # Start Pyrogram client
        await app.start()
        logger.info("✅ Userbot started!")
        
        # Cek koneksi ke Bot A (tanpa kirim pesan)
        try:
            logger.info("🔍 Checking connection to Bot A...")
            user = await app.get_users(BOT_A_CHAT_ID)
            logger.info(f"✅ Bot A is accessible: {user.first_name if user else 'Unknown'}")
        except Exception as e:
            logger.warning(f"⚠️ Bot A not accessible yet: {e}")
            logger.info("⏳ Will try to send messages anyway...")
        
        # Jalankan queue processor
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    asyncio.run(main())
