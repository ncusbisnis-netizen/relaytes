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

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== KONFIGURASI ====================
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')
BOT_B_TOKEN = os.environ.get('BOT_B_TOKEN', '')
BOT_A_USERNAME = 'bengkelmlbb_bot'
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# ==================== COUNTRY MAPPING SEDERHANA (10 NEGARA) ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
    'VN': '🇻🇳 Vietnam',
    'US': '🇺🇸 United States',
    'JP': '🇯🇵 Japan',
    'KR': '🇰🇷 South Korea',
    'CN': '🇨🇳 China',
}

# Default jika negara tidak ada di mapping
DEFAULT_REGION = '🌍 Unknown'

# Validasi environment
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    exit(1)

# ==================== REDIS ====================
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

# ==================== GLOBAL VARIABLES ====================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

bot_status = {'in_captcha': False}
sent_requests = {}          # untuk rate limiting
waiting_for_result = {}     # flag per user (key: chat_id:user_id)
downloaded_photos = []       # untuk cleanup file OCR

# Data request yang sedang aktif (hanya SATU)
active_request = None        # akan berisi dict atau None

# Timer untuk captcha
captcha_timer_task = None

# Konstanta timeout
REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== FUNGSI BANTUAN ====================
def clean_bind_text(text):
    """Bersihkan text bind info"""
    
    # Handle (Private) dan variasinya
    if 'Private' in text:
        text = re.sub(r'Bind\s*\(Private\)', 'Hide information', text)
        text = re.sub(r'\(Private\)', 'Hide information', text)
        text = re.sub(r'\bPrivate\b', 'Hide information', text)
    
    # Handle (Unverified) - hapus saja
    text = re.sub(r'\s*\(Unverified\)', '', text)
    
    # Handle kasus "Moonton Unverified"
    if 'Moonton Unverified' in text:
        if 'Moonton :' in text or 'Moonton:' in text:
            text = re.sub(r'Moonton\s*:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
        else:
            text = re.sub(r'Moonton\s+Unverified', 'Moonton: empty.', text)
    
    # Bersihkan spasi berlebih
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def validate_mlbb_gopay_sync(user_id, server_id):
    """Validasi akun MLBB menggunakan API GoPay"""
    url = 'https://gopay.co.id/games/v1/order/user-account'
    
    headers = {
        'Content-Type': 'application/json',
        'X-Client': 'web-mobile',
        'X-Timestamp': str(int(time.time() * 1000)),
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
    }
    
    body = {
        "code": "MOBILE_LEGENDS",
        "data": {
            "userId": str(user_id).strip(),
            "zoneId": str(server_id).strip()
        }
    }
    
    try:
        logger.info(f"📤 GoPay Request: {user_id}:{server_id}")
        
        response = requests.post(url, headers=headers, json=body, timeout=30)
        logger.info(f"📥 Response status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            return {'status': False, 'message': f'HTTP {response.status_code}'}
        
        result = response.json()
        if not result or 'data' not in result:
            return {'status': False, 'message': 'Invalid response'}
        
        data = result['data']
        username = data.get('username', 'Unknown').replace('+', ' ')
        country = data.get('countryOrigin', 'ID').upper()
        region = country_mapping.get(country, DEFAULT_REGION)
        
        logger.info(f"✅ GoPay SUCCESS: {username} - {region}")
        
        return {
            'status': True,
            'username': username,
            'region': region
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {'status': False, 'message': str(e)}

async def read_number_from_photo_online(message):
    """OCR menggunakan ocr.space dengan timeout 60 detik"""
    try:
        if not OCR_SPACE_API_KEY:
            return None
        
        logger.info("📸 Downloading captcha photo...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        response = requests.post(
            'https://api.ocr.space/parse/image',
            data={
                'base64Image': f'data:image/jpeg;base64,{image_data}',
                'apikey': OCR_SPACE_API_KEY,
                'language': 'eng',
                'OCREngine': '2'
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if not result.get('IsErroredOnProcessing'):
                text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                text = re.sub(r'[^0-9]', '', text)
                match = re.search(r'(\d{6})', text)
                if match:
                    return match.group(1)
        return None
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

def cleanup_downloaded_photos():
    """Hapus file foto sementara"""
    global downloaded_photos
    for photo_path in downloaded_photos[:]:
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
            downloaded_photos.remove(photo_path)
        except:
            pass

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    """Format output final sederhana"""
    
    keywords = ['Moonton', 'VK', 'Google Play', 'Tiktok', 'Facebook', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    
    # Kelompokkan baris
    lines = original_text.split('\n')
    groups = {}
    current_keyword = None
    current_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        if stripped.startswith('✧'):
            if current_keyword:
                groups[current_keyword] = current_lines
            
            if ':' in stripped:
                parts = stripped[1:].strip().split(':', 1)
                keyword_raw = parts[0].strip()
            else:
                keyword_raw = stripped[1:].strip()
            
            current_keyword = keyword_raw
            current_lines = [stripped]
        else:
            if current_keyword:
                current_lines.append(stripped)
    
    if current_keyword:
        groups[current_keyword] = current_lines
    
    bind_info = []
    for kw in keywords:
        if kw in groups:
            lines_group = groups[kw]
            main_line = lines_group[0]
            if main_line.startswith('✧'):
                main_line = main_line[1:].strip()
            
            main_line = clean_bind_text(main_line)
            
            if ':' in main_line:
                label, value = main_line.split(':', 1)
                label = label.strip()
                value = value.strip()
                bind_info.append(f"• {label}: {value}")
            else:
                bind_info.append(f"• {kw}: {main_line}")
        else:
            bind_info.append(f"• {kw}: empty.")
    
    final = f"""INFORMATION ACCOUNT:
ID Server: {uid} ({sid})
Nickname: {nickname}
Region: {region}

BIND INFO:
{chr(10).join(bind_info)}

Device Login: Android {android} | iOS {ios}"""
    
    reply_markup = {
        'inline_keyboard': [
            [{'text': 'Stok Admin', 'url': STOK_ADMIN_URL}]
        ]
    }
    return final, reply_markup

# ==================== FUNGSI KOMUNIKASI DENGAN BOT B ====================
async def send_status_to_user(chat_id, text, reply_to_message_id=None, reply_markup=None):
    """Kirim pesan status ke user melalui Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
    }
    if reply_to_message_id:
        data['reply_to_message_id'] = reply_to_message_id
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()['result']['message_id']
    except:
        pass
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    """Edit pesan yang sudah dikirim ke user"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

# ==================== DETEKSI CAPTCHA ====================
def is_captcha_message(message, text):
    """Deteksi apakah pesan captcha"""
    
    captcha_keywords = ['captcha', 'kode captcha', 'masukkan kode', 'verify', '🔒']
    text_lower = text.lower()
    
    for keyword in captcha_keywords:
        if keyword in text_lower:
            return True
    
    if '🔒 Masukkan kode captcha' in text:
        return True
    
    if message.photo and ('masukkan' in text_lower or 'kode' in text_lower):
        return True
    
    return False

# ==================== HANDLER PESAN DARI BOT A ====================
@events.register(events.NewMessage)
async def message_handler(event):
    global captcha_timer_task, bot_status, active_request

    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    text = message.text or message.message or ''

    # Hanya pesan dari Bot A
    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:50]}")

    # ========== CEK CAPTCHA ==========
    if is_captcha_message(message, text):
        logger.warning("🚫 CAPTCHA terdeteksi!")
        
        if active_request:
            # Reset timeout untuk request yang sedang aktif
            active_request['start_time'] = time.time()
            
            # Update status user
            await edit_status_message(
                active_request['chat_id'],
                active_request['message_id'],
                "⚠️ Captcha terdeteksi, sedang diproses otomatis..."
            )
        
        bot_status['in_captcha'] = True

        # Batalkan timer sebelumnya
        if captcha_timer_task:
            captcha_timer_task.cancel()

        # Timer reset captcha
        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("Captcha timeout, status direset")
            
            if active_request:
                await edit_status_message(
                    active_request['chat_id'],
                    active_request['message_id'],
                    "❌ Gagal memproses captcha. Silakan coba lagi nanti."
                )
                active_request = None
        
        captcha_timer_task = asyncio.create_task(reset_captcha())

        # Ambil kode captcha
        captcha_code = None

        # Cek di teks
        code_match = re.search(r'kode\s*[:\s]*(\d{6})', text, re.IGNORECASE)
        if code_match:
            captcha_code = code_match.group(1)
            logger.info(f"🔑 Kode captcha: {captcha_code}")

        # OCR jika ada foto
        if not captcha_code and message.photo:
            captcha_code = await read_number_from_photo_online(message)
            if captcha_code:
                logger.info(f"🔑 OCR: {captcha_code}")

        if captcha_code and len(captcha_code) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info("📤 Perintah verify dikirim")
            
            if active_request:
                await edit_status_message(
                    active_request['chat_id'],
                    active_request['message_id'],
                    f"✅ Kode captcha terkirim, menunggu verifikasi..."
                )
        else:
            logger.error("❌ Gagal dapat kode captcha")
            cleanup_downloaded_photos()

            if active_request:
                await edit_status_message(
                    active_request['chat_id'],
                    active_request['message_id'],
                    "❌ Gagal memproses captcha. Silakan coba lagi."
                )
                active_request = None

            bot_status['in_captcha'] = False
            if captcha_timer_task:
                captcha_timer_task.cancel()
                captcha_timer_task = None
        
        return

    # ========== HASIL INFO ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info")
        
        if not active_request:
            logger.warning("❌ Tidak ada request aktif")
            return

        # Ambil data dari active_request
        chat_id = active_request['chat_id']
        message_id = active_request['message_id']
        user_id_original = active_request['user_id_original']
        
        logger.info(f"📋 Hasil untuk user {user_id_original}")

        # Ekstrak data
        id_match = re.search(r'ID:?\s*(\d+)', text)
        server_match = re.search(r'Server:?\s*(\d+)', text)
        android_match = re.search(r'Android:?\s*(\d+)', text)
        ios_match = re.search(r'iOS:?\s*(\d+)', text)

        uid = id_match.group(1) if id_match else 'Unknown'
        sid = server_match.group(1) if server_match else 'Unknown'
        android = android_match.group(1) if android_match else '0'
        ios = ios_match.group(1) if ios_match else '0'

        # Validasi via GoPay
        gopay = validate_mlbb_gopay_sync(uid, sid)
        if gopay['status']:
            nickname = gopay['username']
            region = gopay['region']
        else:
            nickname = 'Tidak diketahui'
            region = DEFAULT_REGION

        # Format output
        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)

        # EDIT pesan status
        await edit_status_message(chat_id, message_id, output, markup)

        # Bersihkan
        waiting_key = f"{chat_id}:{user_id_original}"
        waiting_for_result.pop(waiting_key, None)
        
        # Hapus dari Redis
        try:
            r.delete(active_request['req_id'])
        except:
            pass

        cleanup_downloaded_photos()
        
        # Reset active_request
        active_request = None
        
        # Reset captcha status
        bot_status['in_captcha'] = False
        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        
        logger.info(f"✅ Selesai")
        return

    # ========== VERIFIKASI SUKSES ==========
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        logger.info("✅ Verifikasi sukses")
        
        # Matikan status captcha
        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        bot_status['in_captcha'] = False
        
        # Auto-retry untuk request yang sedang aktif
        if active_request:
            await asyncio.sleep(2)
            cmd = f"{active_request['command']} {active_request['args'][0]} {active_request['args'][1]}"
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 Auto-retry: {cmd}")
            active_request['start_time'] = time.time()
            
            await edit_status_message(
                active_request['chat_id'],
                active_request['message_id'],
                "🔄 Verifikasi sukses, mengirim ulang request..."
            )
        return

# ==================== PROSES ANTRIAN ====================
async def process_queue():
    logger.info("🔄 Queue processor started")
    while True:
        try:
            # Hanya proses jika tidak dalam captcha DAN tidak ada request aktif
            if not bot_status['in_captcha'] and not active_request:
                # Ambil request dari Redis (FIFO)
                req_bytes = r.lpop('pending_requests')
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now = time.time()

                    req_json = r.get(req_id)
                    if not req_json:
                        logger.warning(f"⚠️ Request {req_id} tidak ditemukan")
                        continue

                    req_data = json.loads(req_json)
                    
                    # Ambil data
                    chat_id = req_data['chat_id']
                    user_id_original = req_data['user_id']
                    message_id = req_data.get('message_id')
                    command = req_data['command']
                    args = req_data['args']
                    
                    logger.info(f"📋 Memproses request baru")

                    # Kirim status
                    status_text = "⏳ Proses request..."
                    msg_id = await send_status_to_user(
                        chat_id, 
                        status_text,
                        reply_to_message_id=message_id if command == '/cekinfo' else None
                    )
                    
                    if not msg_id:
                        logger.error(f"❌ Gagal kirim status")
                        r.delete(req_id)
                        continue

                    # Simpan ke active_request
                    active_request = {
                        'req_id': req_id,
                        'chat_id': chat_id,
                        'message_id': msg_id,
                        'user_id_original': user_id_original,
                        'start_time': now,
                        'command': command,
                        'args': args
                    }
                    
                    # Kirim ke Bot A
                    cmd = f"{command} {args[0]} {args[1]}"
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Mengirim ke Bot A: {cmd}")
                    
                    # Rate limiting
                    sent_requests[req_id] = now
                    
                    # Set waiting flag
                    waiting_key = f"{chat_id}:{user_id_original}"
                    waiting_for_result[waiting_key] = True
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot...")

    # Bersihkan queue lama
    try:
        queue_len = r.llen('pending_requests')
        if queue_len > 0:
            logger.info(f"🧹 Membersihkan {queue_len} request lama...")
            for _ in range(queue_len):
                r.lpop('pending_requests')
        keys = r.keys('req:*')
        if keys:
            for key in keys:
                r.delete(key)
    except Exception as e:
        logger.error(f"❌ Gagal bersihkan Redis: {e}")

    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Login sebagai: {me.first_name}")

        client.add_event_handler(message_handler)
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
