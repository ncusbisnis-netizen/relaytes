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

# ==================== COUNTRY MAPPING (HANYA 5) ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
}

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
waiting_for_result = {}     # flag per user
downloaded_photos = []       # untuk cleanup file OCR

# Data request yang sedang aktif (hanya satu dalam satu waktu)
active_requests = {}        # key: req_id, value: dict {chat_id, message_id, start_time, command, args}

# Timer untuk captcha (agar tidak stuck selamanya)
captcha_timer_task = None

# Konstanta timeout
REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 60  # Ditambah jadi 60 detik untuk captcha

# ==================== FUNGSI BANTUAN ====================
def clean_bind_text(text):
    """Bersihkan text bind info"""
    # 1. Handle (Private) dan variasinya
    text = re.sub(r'\(Private\)', 'Hide information', text)
    text = re.sub(r'Bind \(Private\)', 'Hide information', text)
    text = re.sub(r'Private', 'Hide information', text)
    
    # 2. Handle Moonton Unverified (khusus Moonton)
    if 'Moonton Unverified' in text:
        parts = text.split('Moonton :', 1)
        if len(parts) > 1:
            text = f"{parts[0]}Moonton : empty."
    
    # 3. Handle (Unverified) untuk yang lain
    text = re.sub(r'\(Unverified\)', 'Failed Verification', text)
    text = re.sub(r'Unverified', 'Failed Verification', text)
    
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
        region = country_mapping.get(country, f'🌍 {country}')
        
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
    """OCR menggunakan ocr.space dengan multiple engine dan retry"""
    try:
        if not OCR_SPACE_API_KEY:
            logger.error("❌ OCR API Key tidak ditemukan")
            return None
        
        logger.info("📸 Downloading captcha photo...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        # Coba dengan multiple OCR engines
        ocr_engines = ['2', '1', '3']  # Coba engine 2, 1, dan 3
        
        for engine in ocr_engines:
            try:
                logger.info(f"🔍 Mencoba OCR dengan engine {engine}...")
                
                with open(photo_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                response = requests.post(
                    'https://api.ocr.space/parse/image',
                    data={
                        'base64Image': f'data:image/jpeg;base64,{image_data}',
                        'apikey': OCR_SPACE_API_KEY,
                        'language': 'eng',
                        'OCREngine': engine,
                        'scale': 'true',
                        'detectOrientation': 'true',
                        'filetype': 'JPG'
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if not result.get('IsErroredOnProcessing'):
                        text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                        logger.info(f"📝 OCR Result (engine {engine}): {text}")
                        
                        # Bersihkan text - hanya ambil angka
                        text = re.sub(r'[^0-9]', '', text)
                        
                        # Cari 6 digit angka berturut-turut
                        match = re.search(r'(\d{6})', text)
                        if match:
                            code = match.group(1)
                            logger.info(f"✅ Kode ditemukan dengan engine {engine}: {code}")
                            return code
                        
                        # Coba juga cari angka yang mungkin terpisah tapi total 6 digit
                        if len(text) >= 6:
                            code = text[:6]
                            logger.info(f"✅ Mengambil 6 digit pertama: {code}")
                            return code
                            
            except Exception as e:
                logger.error(f"❌ OCR engine {engine} error: {e}")
                continue
            
            await asyncio.sleep(1)
        
        return None
        
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None
    finally:
        # Cleanup
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
                if photo_path in downloaded_photos:
                    downloaded_photos.remove(photo_path)
        except:
            pass

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
    """Format output final dengan penanganan Moonton empty yang benar"""
    
    keywords = ['Moonton', 'VK', 'Google Play', 'Tiktok', 'Facebook', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    
    # Kelompokkan baris berdasarkan keyword utama (diawali ✧)
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
            
            # Ambil nama keyword (sebelum ':')
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
            
            if kw == "Moonton":
                # Cari sub-baris yang diawali '-'
                sub_lines = [l for l in lines_group if l.startswith('-')]
                
                if sub_lines:
                    # Ada beberapa akun Moonton, tampilkan masing-masing
                    for sub in sub_lines:
                        sub_clean = sub.lstrip('-').strip()
                        if ':' in sub_clean:
                            label, value = sub_clean.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            # Bersihkan value
                            value = clean_bind_text(value)
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• {sub_clean}")
                else:
                    # Hanya satu baris Moonton
                    main_line = lines_group[0]
                    # Hapus '✧' dan bersihkan
                    if main_line.startswith('✧'):
                        main_line = main_line[1:].strip()
                    
                    # Cek apakah ini baris empty
                    if 'empty' in main_line.lower():
                        # Format dengan benar
                        if ':' in main_line:
                            parts = main_line.split(':', 1)
                            label = parts[0].strip()
                            if label.count('Moonton') > 1:
                                label = 'Moonton'
                            bind_info.append(f"• {label}: empty.")
                        else:
                            bind_info.append(f"• Moonton: empty.")
                    else:
                        # Tidak empty, proses normal
                        main_line = clean_bind_text(main_line)
                        
                        if ':' in main_line:
                            label, value = main_line.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• Moonton: {main_line}")
            else:
                # Keyword lain: ambil baris utama saja
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
            # Keyword tidak ditemukan
            bind_info.append(f"• {kw}: empty.")
    
    final = f"""INFORMATION ACCOUNT:
ID: {uid}
Server: {sid}
Nickname: {nickname}
Region: {region}

BIND INFO:
{chr(10).join(bind_info)}

Device Login: Android {android} | iOS {ios}"""
    
    reply_markup = {
        'inline_keyboard': [
            [{'text': 'STOK ADMIN', 'url': STOK_ADMIN_URL}]
        ]
    }
    return final, reply_markup

# ==================== FUNGSI KOMUNIKASI DENGAN BOT B ====================
async def send_status_to_user(chat_id, text, reply_markup=None):
    """Kirim pesan status ke user melalui Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        logger.info(f"📤 Mengirim status ke user {chat_id}: {text[:50]}...")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            msg_id = response.json()['result']['message_id']
            logger.info(f"✅ Status terkirim, message_id: {msg_id}")
            return msg_id
        else:
            logger.error(f"❌ Gagal kirim status: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Exception kirim status: {e}")
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    """Edit pesan yang sudah dikirim ke user melalui Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        logger.info(f"✏️ Mengedit pesan {message_id} untuk user {chat_id}")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Pesan {message_id} berhasil diedit")
        else:
            logger.error(f"❌ Gagal edit pesan {message_id}: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Exception saat edit pesan: {e}")

# ==================== TIMEOUT CHECKER ====================
async def timeout_checker():
    """Loop untuk memonitor request yang melebihi batas waktu"""
    while True:
        # Jika sedang dalam captcha, timeout ditangguhkan
        if bot_status['in_captcha']:
            await asyncio.sleep(1)
            continue

        now = time.time()
        to_remove = []
        for req_id, req_data in list(active_requests.items()):
            if now - req_data['start_time'] > REQUEST_TIMEOUT:
                logger.warning(f"⏰ Timeout untuk request {req_id}")
                await edit_status_message(
                    req_data['chat_id'],
                    req_data['message_id'],
                    "Request timeout. Silakan coba lagi."
                )
                # Hapus dari Redis
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                    logger.info(f"🗑️ Request {req_id} dihapus dari Redis karena timeout")
                except Exception as e:
                    logger.error(f"❌ Gagal hapus Redis saat timeout: {e}")
                # Hapus dari waiting flag
                waiting_for_result.pop(req_data['chat_id'], None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)
            logger.info(f"🗑️ Request {req_id} dihapus dari active_requests karena timeout")
        await asyncio.sleep(1)

# ==================== HANDLER PESAN DARI BOT A ====================
@events.register(events.NewMessage)
async def message_handler(event):
    global captcha_timer_task, bot_status

    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    text = message.text or message.message or ''

    # Hanya pesan dari Bot A yang diproses
    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # ========== 1. HASIL INFO ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info dari Bot A")
        
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif, hasil diabaikan")
            return

        req_id, req_info = next(iter(active_requests.items()))
        user_id = req_info['chat_id']
        message_id = req_info['message_id']
        logger.info(f"📋 Request aktif ditemukan: {req_id} untuk user {user_id}")

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
            region = '🌍 Tidak diketahui'

        # Format output
        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)

        # Edit pesan status dengan hasil
        await edit_status_message(user_id, message_id, output, markup)

        # Bersihkan data dari memori
        try:
            del active_requests[req_id]
            waiting_for_result.pop(user_id, None)
            logger.info(f"✅ Request {req_id} dihapus dari active_requests")
        except Exception as e:
            logger.error(f"❌ Gagal hapus active_requests: {e}")

        # Hapus dari Redis
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id:
                r.lpop('pending_requests')
            r.delete(req_id)
            logger.info(f"✅ Request {req_id} dihapus dari Redis")
        except Exception as e:
            logger.error(f"❌ Gagal hapus Redis: {e}")

        cleanup_downloaded_photos()
        return

    # ========== 2. VERIFIKASI BERHASIL ==========
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        logger.info("🎉 VERIFIKASI BERHASIL!")
        
        # Matikan timer captcha
        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        bot_status['in_captcha'] = False
        
        # Update status ke user
        if active_requests:
            req_id, req_info = next(iter(active_requests.items()))
            await edit_status_message(
                req_info['chat_id'],
                req_info['message_id'],
                "✅ Verifikasi berhasil! Melanjutkan proses..."
            )
        
        # Auto-retry untuk request yang sedang aktif
        if active_requests:
            logger.info("⏳ Menunggu 3 detik sebelum auto-retry...")
            await asyncio.sleep(3)
            
            req_id, req_info = next(iter(active_requests.items()))
            cmd = f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}"
            
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 Auto-retry: {cmd}")
            
            # Update waktu mulai
            req_info['start_time'] = time.time()
        else:
            logger.warning("⚠️ Tidak ada request aktif untuk auto-retry")
        
        return

    # ========== 3. CAPTCHA - VERSI AGGRESIF ==========
    if (message.photo or 
        'captcha' in text.lower() or 
        'kode' in text.lower() or
        re.search(r'\d{6}', text) or 
        '🔒 Masukkan kode captcha' in text):
        
        logger.warning("🚫 CAPTCHA terdeteksi!")
        bot_status['in_captcha'] = True

        # Reset timeout untuk request yang sedang aktif
        if active_requests:
            for req_id, req_info in active_requests.items():
                req_info['start_time'] = time.time()
                logger.info(f"⏱️ Reset timeout untuk request {req_id} karena captcha")
                
                # Update status ke user
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "⏳ Captcha terdeteksi, sedang memproses..."
                )
        else:
            logger.warning("⚠️ Captcha terdeteksi tapi tidak ada request aktif")

        # Batalkan timer sebelumnya jika ada
        if captcha_timer_task:
            captcha_timer_task.cancel()

        # Set timer untuk captcha
        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("Captcha timeout, status direset")
        captcha_timer_task = asyncio.create_task(reset_captcha())

        # AGGRESSIVE CAPTCHA HANDLING
        captcha_code = None
        
        # Method 1: Cek di teks
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"🔑 [Method 1] Kode dari teks: {captcha_code}")
        
        # Method 2: OCR dengan multiple attempts
        if not captcha_code and message.photo:
            for attempt in range(3):  # Coba 3 kali
                logger.info(f"📸 [Method 2] Percobaan OCR ke-{attempt+1}/3")
                captcha_code = await read_number_from_photo_online(message)
                
                if captcha_code:
                    logger.info(f"🔑 [Method 2] Kode dari OCR (percobaan {attempt+1}): {captcha_code}")
                    break
                else:
                    logger.warning(f"⚠️ OCR percobaan {attempt+1} gagal")
                    
                if attempt < 2:
                    await asyncio.sleep(3)
        
        # Method 3: Cari pola di teks
        if not captcha_code:
            pattern = r'kode[:\s]*(\d{6})'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                captcha_code = match.group(1)
                logger.info(f"🔑 [Method 3] Kode dari pola teks: {captcha_code}")
        
        # Method 4: Coba dari caption foto
        if not captcha_code and message.photo and message.message:
            digits_in_caption = re.findall(r'\d', message.message)
            if len(digits_in_caption) >= 6:
                captcha_code = ''.join(digits_in_caption[:6])
                logger.info(f"🔑 [Method 4] Kode dari caption: {captcha_code}")
        
        # Method 5: Fallback - coba /verify tanpa kode
        if not captcha_code:
            logger.error("❌ SEMUA METODE GAGAL MENDAPATKAN KODE CAPTCHA")
            
            await client.send_message(BOT_A_USERNAME, "/verify")
            logger.info("📤 Mengirim /verify tanpa kode sebagai percobaan")
            
            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "⚠️ Gagal membaca kode captcha. Mencoba lagi..."
                )
            return

        # Jika berhasil mendapatkan kode
        if captcha_code and len(captcha_code) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info(f"📤 Perintah verify {captcha_code} dikirim")
            
            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    f"✅ Kode captcha terdeteksi: {captcha_code}\n⏳ Menunggu verifikasi..."
                )
            
            # Tunggu respon verifikasi
            await asyncio.sleep(5)
            
            # Cek apakah masih dalam captcha
            if bot_status['in_captcha']:
                logger.warning("⚠️ Verifikasi mungkin gagal, mencoba lagi...")
                await asyncio.sleep(3)
        else:
            logger.error(f"❌ Kode captcha tidak valid: {captcha_code}")
            cleanup_downloaded_photos()

# ==================== PROSES ANTRIAN ====================
async def process_queue():
    logger.info("🔄 Queue processor started")
    while True:
        try:
            if not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now = time.time()

                    # Rate limit
                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2)
                        continue

                    req_json = r.get(req_id)
                    if not req_json:
                        logger.warning(f"⚠️ Request {req_id} tidak ditemukan di Redis")
                        r.lpop('pending_requests')
                        continue

                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                    logger.info(f"📋 Memproses request {req_id} dari user {user_id}")

                    if waiting_for_result.get(user_id, False):
                        logger.info(f"⏳ User {user_id} masih menunggu, pindahkan ke belakang")
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue

                    # Kirim status ke user
                    status_text = "Proses request..."
                    msg_id = await send_status_to_user(user_id, status_text)
                    if not msg_id:
                        logger.error(f"❌ Gagal mengirim status ke user {user_id}")
                        r.lpop('pending_requests')
                        r.delete(req_id)
                        continue

                    # Simpan ke active_requests
                    active_requests[req_id] = {
                        'chat_id': user_id,
                        'message_id': msg_id,
                        'start_time': now,
                        'command': req_data['command'],
                        'args': req_data['args']
                    }
                    logger.info(f"✅ Request {req_id} disimpan ke active_requests")

                    # Kirim perintah ke Bot A
                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Mengirim ke Bot A: {cmd}")

                    sent_requests[req_id] = now
                    waiting_for_result[user_id] = True
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error di process_queue: {e}")
        await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot dengan OCR agresif...")

    # Bersihkan queue lama di Redis
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
                logger.info(f"🗑️ Menghapus key Redis: {key}")
    except Exception as e:
        logger.error(f"❌ Gagal membersihkan Redis: {e}")

    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Login sebagai: {me.first_name}")

        # Daftarkan event handler
        client.add_event_handler(message_handler)

        # Jalankan timeout checker
        asyncio.create_task(timeout_checker())

        # Jalankan pemrosesan antrian
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
