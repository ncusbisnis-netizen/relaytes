import requests
import asyncio
import os
import time
import re
import logging
import json
import redis
from pyrogram import Client, filters, handlers
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler, RawUpdateHandler
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

# Pyrogram Client dengan konfigurasi khusus
app = Client(
    name="relay_bot",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
    workers=4,  # Tambah worker untuk menerima update
    sleep_threshold=30,
    test_mode=False,
    no_updates=False,  # Pastikan tidak memblokir update
    takeout=False,
    max_concurrent_transmissions=4
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

# ==================== HANDLER UTAMA PESAN ====================

async def message_handler(client, message: Message):
    """
    Handler untuk semua pesan - dipanggil secara eksplisit
    """
    # LOG LENGKAP
    logger.info("=" * 80)
    logger.info("🔥🔥🔥 MESSAGE HANDLER TRIGGERED 🔥🔥🔥")
    logger.info(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📌 Message ID: {message.id}")
    logger.info(f"💬 Chat ID: {message.chat.id}")
    logger.info(f"💬 Chat Type: {message.chat.type}")
    logger.info(f"👤 From User ID: {message.from_user.id if message.from_user else 'None'}")
    logger.info(f"👤 From Username: @{message.from_user.username if message.from_user and message.from_user.username else 'None'}")
    logger.info(f"👤 From First Name: {message.from_user.first_name if message.from_user else 'None'}")
    logger.info(f"🤖 Is Bot: {message.from_user.is_bot if message.from_user else 'N/A'}")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"📝 Text: '{message.text or message.caption or ''}'")
    logger.info("=" * 80)
    
    # Ambil teks dari mana pun
    text = message.text or message.caption or ''
    
    # CEK APAKAH DARI BOT A
    from_bot_a = False
    
    # Cek 1: Chat ID
    if message.chat.id == BOT_A_CHAT_ID:
        from_bot_a = True
        logger.info("✅✅✅ MATCH: Chat ID = Bot A")
    
    # Cek 2: From User ID
    if message.from_user and message.from_user.id == BOT_A_CHAT_ID:
        from_bot_a = True
        logger.info("✅✅✅ MATCH: User ID = Bot A")
    
    # Cek 3: Username
    if message.from_user and message.from_user.username and message.from_user.username.lower() == 'bengkelmlbb_bot':
        from_bot_a = True
        logger.info("✅✅✅ MATCH: Username = Bot A")
    
    if from_bot_a:
        logger.info("🚨🚨🚨 INI PESAN DARI BOT A! WAJIB DIPROSES!")
        await process_bot_a_message(client, message)
    else:
        logger.info("❌ Bukan dari Bot A, diabaikan")

async def process_bot_a_message(client, message: Message):
    """
    Proses khusus untuk pesan dari Bot A
    """
    text = message.text or message.caption or ''
    
    logger.info("=" * 80)
    logger.info("🎯🎯🎯 MEMPROSES PESAN DARI BOT A 🎯🎯🎯")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"📝 Full Text: '{text}'")
    logger.info("=" * 80)
    
    # ===== CEK CAPTCHA =====
    is_captcha = False
    captcha_code = None
    
    # Ciri 1: Ada foto (pasti captcha)
    if message.photo:
        logger.info("📸 FOTO DARI BOT A - PASTI CAPTCHA")
        is_captcha = True
        
        # Ambil dari caption jika ada
        if text:
            six_digit = re.findall(r'(\d{6})', text)
            if six_digit:
                captcha_code = six_digit[0]
                logger.info(f"✅ Captcha dari caption: {captcha_code}")
    
    # Ciri 2: Teks mengandung angka 6 digit + kata kunci
    if not captcha_code and text:
        six_digit = re.findall(r'(\d{6})', text)
        if six_digit:
            keywords = ['captcha', 'verify', 'code', 'enter', 'verification', 'kode']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = six_digit[0]
                logger.info(f"✅ Captcha dari teks: {captcha_code}")
    
    # Ciri 3: Baris pertama 6 digit
    if not captcha_code and text:
        lines = text.strip().split('\n')
        if lines and lines[0].strip().isdigit() and len(lines[0].strip()) == 6:
            is_captcha = True
            captcha_code = lines[0].strip()
            logger.info(f"✅ Captcha dari baris pertama: {captcha_code}")
    
    # ===== JIKA CAPTCHA =====
    if is_captcha:
        logger.warning("🚫🚫🚫 CAPTCHA DARI BOT A TERDETEKSI!")
        
        # Jika captcha_code belum ada (foto tanpa teks), pakai OCR
        if not captcha_code and message.photo:
            logger.info("🔍 Tidak ada teks, mencoba OCR...")
            captcha_code = await read_number_from_photo(message)
        
        if captcha_code:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # Kirim verifikasi ke Bot A
            await client.send_message(BOT_A_CHAT_ID, f"/verify {captcha_code}")
            logger.info(f"📤📤📤 Verifikasi dikirim: /verify {captcha_code}")
            
            # Tunggu sebentar
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            logger.info("✅ Captcha selesai diproses")
            
            # Proses ulang request pending
            await retry_pending_requests()
        else:
            logger.error("❌❌❌ Gagal mendapatkan kode captcha")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
        
        return
    
    # ===== BUKAN CAPTCHA - MUNGKIN HASIL INFO =====
    if text:
        logger.info("📨📨📨 Memproses sebagai hasil info")
        
        # Ambil request dari queue
        request_id = r.lpop('pending_requests')
        
        if request_id:
            request_id = request_id.decode('utf-8')
            logger.info(f"📋 Memproses request ID: {request_id}")
            
            request_data_json = r.get(request_id)
            
            if request_data_json is None:
                logger.warning(f"⚠️ Request {request_id} expired")
                return
            
            request_data = json.loads(request_data_json)
            user_id = request_data['chat_id']
            logger.info(f"👤 Forward ke user: {user_id}")
            
            # Kirim ke user via Bot B
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': user_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            logger.info(f"📤 Mengirim ke Bot B...")
            
            try:
                response = requests.post(url, json=data, timeout=10)
                logger.info(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"✅✅✅ SUCCESS: Terkirim ke user {user_id}")
                    r.delete(request_id)
                else:
                    logger.error(f"❌ Gagal forward: {response.status_code}")
                    r.rpush('pending_requests', request_id)
                    
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
                r.rpush('pending_requests', request_id)
    else:
        logger.warning("⚠️ Pesan dari Bot A tanpa teks (mungkin media saja)")

# ==================== RAW UPDATE HANDLER (UNTUK DEBUG) ====================

async def raw_update_handler(client, update, users, chats):
    """
    Handler untuk menangkap SEMUA update mentah dari Telegram
    """
    logger.info("📡📡📡 RAW UPDATE RECEIVED 📡📡📡")
    logger.info(f"Update type: {type(update)}")
    logger.info(f"Update: {update}")
    
    # Cek apakah ini update pesan
    if hasattr(update, 'message'):
        logger.info("Ini adalah update pesan!")
    elif hasattr(update, 'channel_post'):
        logger.info("Ini adalah channel post!")

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """
    Kirim ulang request yang pending setelah captcha selesai
    """
    logger.info("🔄 Memproses ulang request pending...")
    
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
        logger.info(f"✅ Meretry {retry_count} request")

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
                            logger.info(f"⏳ Request {request_id} sudah dikirim {time_diff:.1f}s lalu, menunggu...")
                            await asyncio.sleep(5)
                            continue
                        elif time_diff > 120:  # Lebih dari 2 menit, anggap expired
                            logger.warning(f"⚠️ Request {request_id} expired (>2 menit), hapus dari queue")
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
                    logger.info(f"📤 Mengirim ke Bot A: {cmd}")
                    
                    try:
                        await app.send_message(BOT_A_CHAT_ID, cmd)
                        logger.info(f"✅ Terkirim ke Bot A: {cmd}")
                        
                        # Catat waktu pengiriman
                        sent_requests[request_id] = current_time
                        
                    except Exception as e:
                        logger.error(f"❌ Gagal kirim ke Bot A: {e}")
                        
                        # Kalau error, tunggu sebentar
                        if "PEER_ID_INVALID" in str(e):
                            logger.warning("⏳ Bot A tidak siap, menunggu 30 detik...")
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
        # Daftarkan handler secara manual
        app.add_handler(MessageHandler(message_handler))
        app.add_handler(RawUpdateHandler(raw_update_handler))
        
        # Start Pyrogram client
        await app.start()
        logger.info("✅ Userbot started!")
        
        # Informasi user
        me = await app.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        logger.info(f"✅ User ID: {me.id}")
        
        # Coba koneksi ke Bot A
        try:
            bot_info = await app.get_users(BOT_A_CHAT_ID)
            logger.info(f"✅ Bot A info: {bot_info.first_name}")
        except Exception as e:
            logger.warning(f"⚠️ Cannot get Bot A info: {e}")
        
        # Jalankan queue processor
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    asyncio.run(main())
