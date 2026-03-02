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
import base64
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
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')

# Validasi environment
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, BOT_A_CHAT_ID, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    exit(1)

if not OCR_SPACE_API_KEY:
    logger.warning("⚠️ OCR_SPACE_API_KEY tidak ditemukan! OCR online tidak akan berfungsi.")

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
waiting_for_result = {}  # State untuk tracking apakah sedang menunggu hasil info

# ==================== OCR ONLINE FUNCTION ====================

async def read_number_from_photo_online(message):
    """Baca angka 6 digit dari foto captcha menggunakan OCR.space API"""
    try:
        if not OCR_SPACE_API_KEY:
            logger.error("❌ OCR_SPACE_API_KEY tidak tersedia")
            return None
        
        logger.info("📸 OCR Online: Downloading captcha photo...")
        
        # Download foto
        photo_path = await message.download_media()
        logger.info(f"✅ Photo downloaded: {photo_path}")
        
        # Baca file sebagai base64
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Hapus file setelah dibaca
        os.remove(photo_path)
        
        # OCR.space API endpoint
        url = 'https://api.ocr.space/parse/image'
        
        # Payload untuk API
        payload = {
            'base64Image': f'data:image/jpeg;base64,{image_data}',
            'apikey': OCR_SPACE_API_KEY,
            'language': 'eng',
            'OCREngine': '2',
            'isTable': 'false',
            'scale': 'true',
            'detectOrientation': 'true'
        }
        
        logger.info("📤 Sending to OCR.space API...")
        
        # Kirim request
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('IsErroredOnProcessing') == False:
                if result.get('ParsedResults') and len(result['ParsedResults']) > 0:
                    text = result['ParsedResults'][0].get('ParsedText', '')
                    
                    # Bersihkan hasil (ambil hanya angka)
                    text = re.sub(r'[^0-9]', '', text)
                    logger.info(f"📝 OCR result: '{text}'")
                    
                    # Cari 6 digit
                    match = re.search(r'(\d{6})', text)
                    if match:
                        code = match.group(1)
                        logger.info(f"✅ OCR Online success: {code}")
                        return code
                    else:
                        logger.warning("❌ No 6-digit found in OCR result")
            else:
                error = result.get('ErrorMessage', ['Unknown error'])[0]
                logger.error(f"❌ OCR Error: {error}")
        else:
            logger.error(f"❌ API Error: {response.status_code}")
            
        return None
        
    except Exception as e:
        logger.error(f"❌ OCR Online error: {e}")
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
    logger.info(f"📋 Current waiting_for_result: {waiting_for_result.get(chat_id, False)}")
    
    # CEK APAKAH DARI BOT A
    if chat_id != BOT_A_CHAT_ID and sender_id != BOT_A_CHAT_ID:
        logger.info("❌ Bukan dari Bot A")
        logger.info("=" * 80)
        return
    
    logger.info("🎯🎯🎯 PESAN DARI BOT A DITERIMA!")
    
    # ===== CEK APAKAH INI PESAN VERIFIKASI SUKSES =====
    if text and ('verification successful' in text.lower() or 'verified' in text.lower()):
        logger.info("✅ Captcha verification successful - IGNORED (not forwarded)")
        logger.info(f"📋 Still waiting for result: {waiting_for_result.get(chat_id, False)}")
        logger.info("=" * 80)
        return
    
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
        
        # SET STATE bahwa kita sedang menunggu hasil info (WAJIB ADA!)
        waiting_for_result[chat_id] = True
        logger.info(f"📋 Waiting for result SET to: {waiting_for_result[chat_id]}")
        
        # Jika captcha_code belum ada (foto tanpa teks), pakai OCR ONLINE
        if not captcha_code and message.photo:
            logger.info("🔍 No text code found, trying OCR online...")
            captcha_code = await read_number_from_photo_online(message)
        
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
            
            # Proses ulang request pending (TAPI STATE TETAP TRUE)
            await retry_pending_requests()
            
            logger.info(f"📋 Waiting for result masih: {waiting_for_result[chat_id]}")
        else:
            logger.error("❌❌❌ Gagal mendapatkan captcha code")
            logger.info("⏳ Menunggu 60 detik sebelum coba lagi...")
            await asyncio.sleep(60)
            bot_status['in_captcha'] = False
            # STATE TETAP TRUE KARENA AKAN COBA LAGI NANTI
        
        logger.info("=" * 80)
        return
    
    # ===== BUKAN CAPTCHA - CEK APAKAH INI HASIL INFO =====
    # Cek apakah kita sedang menunggu hasil
    if waiting_for_result.get(chat_id, False):
        logger.info("📨📨📨 Hasil info dari Bot A - FORWARDING TO USER")
        
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
                    
                    # RESET STATE setelah berhasil forward
                    waiting_for_result[chat_id] = False
                    logger.info(f"📋 Waiting for result RESET to: {waiting_for_result[chat_id]}")
                else:
                    logger.error(f"❌ Gagal forward: {response.status_code}")
                    r.rpush('pending_requests', request_id)
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
                r.rpush('pending_requests', request_id)
        else:
            logger.warning("⚠️ Tidak ada request pending")
    else:
        logger.info("❌ Pesan dari Bot A tapi tidak menunggu hasil - IGNORED")
        logger.info(f"📋 waiting_for_result = {waiting_for_result.get(chat_id, False)}")
    
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
    global sent_requests, waiting_for_result
    sent_requests = {}
    waiting_for_result = {}
    
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
