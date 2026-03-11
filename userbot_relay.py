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

# ==================== COUNTRY MAPPING ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia', 'MY': '🇲🇾 Malaysia', 'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines', 'TH': '🇹🇭 Thailand', 'VN': '🇻🇳 Vietnam',
    'MM': '🇲🇲 Myanmar', 'KH': '🇰🇭 Cambodia', 'LA': '🇱🇦 Laos',
    'BN': '🇧🇳 Brunei', 'TL': '🇹🇱 Timor Leste',
    'US': '🇺🇸 United States', 'GB': '🇬🇧 United Kingdom',
    'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'CN': '🇨🇳 China',
    'IN': '🇮🇳 India', 'PK': '🇵🇰 Pakistan', 'BD': '🇧🇩 Bangladesh',
    'SA': '🇸🇦 Saudi Arabia', 'AE': '🇦🇪 UAE', 'QA': '🇶🇦 Qatar',
    'EG': '🇪🇬 Egypt', 'ZA': '🇿🇦 South Africa', 'NG': '🇳🇬 Nigeria',
    'BR': '🇧🇷 Brazil', 'MX': '🇲🇽 Mexico', 'AR': '🇦🇷 Argentina',
    'DE': '🇩🇪 Germany', 'FR': '🇫🇷 France', 'IT': '🇮🇹 Italy',
    'ES': '🇪🇸 Spain', 'NL': '🇳🇱 Netherlands', 'BE': '🇧🇪 Belgium',
    'CH': '🇨🇭 Switzerland', 'AT': '🇦🇹 Austria', 'SE': '🇸🇪 Sweden',
    'NO': '🇳🇴 Norway', 'DK': '🇩🇰 Denmark', 'FI': '🇫🇮 Finland',
    'PL': '🇵🇱 Poland', 'CZ': '🇨🇿 Czech Republic', 'HU': '🇭🇺 Hungary',
    'GR': '🇬🇷 Greece', 'TR': '🇹🇷 Turkey', 'RU': '🇷🇺 Russia',
    'UA': '🇺🇦 Ukraine', 'BY': '🇧🇾 Belarus', 'RO': '🇷🇴 Romania',
    'BG': '🇧🇬 Bulgaria', 'RS': '🇷🇸 Serbia', 'HR': '🇭🇷 Croatia',
    'AU': '🇦🇺 Australia', 'NZ': '🇳🇿 New Zealand',
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
waiting_for_result = {}     # flag per user (key: chat_id:user_id)
downloaded_photos = []       # untuk cleanup file OCR

# Data request yang sedang aktif
active_requests = {}        # key: req_id, value: dict lengkap

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
    
    # Handle kasus "Moonton Unverified" (tanpa kurung)
    if 'Moonton Unverified' in text:
        if 'Moonton :' in text or 'Moonton:' in text:
            text = re.sub(r'Moonton\s*:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
            text = re.sub(r'Moonton:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
        else:
            text = re.sub(r'Moonton\s+Unverified', 'Moonton: empty.', text)
    
    # CEK KHUSUS: Jika teks mengandung "empty" dan "Moonton" dua kali
    if 'empty' in text.lower() and text.count('Moonton') > 1:
        parts = text.split('empty', 1)
        before_empty = parts[0]
        if 'Moonton' in before_empty:
            moonton_parts = before_empty.split('Moonton')
            if len(moonton_parts) > 1:
                text = f"Moonton: empty.{parts[1] if len(parts) > 1 else ''}"
    
    # HAPUS TITIK GANDA
    text = re.sub(r'empty\.\.', 'empty.', text)
    text = re.sub(r'empty\.\.', 'empty.', text)
    
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
                sub_lines = [l for l in lines_group if l.startswith('-')]
                
                if sub_lines:
                    for sub in sub_lines:
                        sub_clean = sub.lstrip('-').strip()
                        if ':' in sub_clean:
                            label, value = sub_clean.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            value = clean_bind_text(value)
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• {sub_clean}")
                else:
                    main_line = lines_group[0]
                    if main_line.startswith('✧'):
                        main_line = main_line[1:].strip()
                    
                    if 'empty' in main_line.lower():
                        if ':' in main_line:
                            parts = main_line.split(':', 1)
                            label = parts[0].strip()
                            if label.count('Moonton') > 1:
                                label = 'Moonton'
                            bind_info.append(f"• {label}: empty.")
                        else:
                            bind_info.append(f"• Moonton: empty.")
                    else:
                        main_line = clean_bind_text(main_line)
                        if ':' in main_line:
                            label, value = main_line.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• Moonton: {main_line}")
            else:
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
    """Kirim pesan status ke user melalui Bot B (bisa reply)"""
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
        logger.info(f"📤 Mengirim ke user {chat_id}" + 
                   (f" (reply to {reply_to_message_id})" if reply_to_message_id else ""))
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            msg_id = response.json()['result']['message_id']
            logger.info(f"✅ Terkirim, message_id: {msg_id}")
            return msg_id
        else:
            logger.error(f"❌ Gagal: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Exception: {e}")
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
        logger.info(f"✏️ Mengedit pesan {message_id}")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Pesan {message_id} berhasil diedit")
        else:
            logger.error(f"❌ Gagal edit: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Exception: {e}")

# ==================== TIMEOUT CHECKER ====================
async def timeout_checker():
    """Loop untuk memonitor request yang melebihi batas waktu"""
    while True:
        if bot_status['in_captcha']:
            await asyncio.sleep(1)
            continue

        now = time.time()
        to_remove = []
        for req_id, req_data in list(active_requests.items()):
            if now - req_data['start_time'] > REQUEST_TIMEOUT:
                logger.warning(f"⏰ Timeout request {req_id}")
                await edit_status_message(
                    req_data['chat_id'],
                    req_data['message_id'],
                    "Request timeout. Silakan coba lagi."
                )
                try:
                    r.delete(req_id)
                except:
                    pass
                waiting_for_result.pop(f"{req_data['chat_id']}:{req_data['user_id_original']}", None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)
        await asyncio.sleep(1)

# ==================== HANDLER PESAN DARI BOT A ====================
@events.register(events.NewMessage)
async def message_handler(event):
    global captcha_timer_task, bot_status

    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    text = message.text or message.message or ''

    # Hanya pesan dari Bot A
    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # ========== 1. HASIL INFO ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info")
        
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif")
            return

        req_id, req_info = next(iter(active_requests.items()))
        
        chat_id = req_info['chat_id']
        message_id = req_info['message_id']
        user_id_original = req_info['user_id_original']
        original_message_id = req_info.get('original_message_id')
        command = req_info['command']
        
        logger.info(f"📋 Hasil untuk user {user_id_original} di chat {chat_id} (cmd: {command})")

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

        # EDIT pesan status
        await edit_status_message(chat_id, message_id, output, markup)

        # Bersihkan
        del active_requests[req_id]
        waiting_for_result.pop(f"{chat_id}:{user_id_original}", None)
        try:
            r.delete(req_id)
        except:
            pass

        cleanup_downloaded_photos()
        logger.info(f"✅ Selesai untuk user {user_id_original}")
        return

    # ========== 2. VERIFIKASI SUKSES ==========
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        logger.info("✅ Verifikasi sukses, auto-retry dalam 5 detik")

        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        bot_status['in_captcha'] = False

        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            cmd = f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}"
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 Auto-retry: {cmd}")
            req_info['start_time'] = time.time()
        return

    # ========== 3. CAPTCHA ==========
    if (message.photo or 
        'captcha' in text.lower() or 
        re.search(r'\d{6}', text) or 
        '🔒 Masukkan kode captcha' in text):
        
        logger.warning("🚫 CAPTCHA terdeteksi!")
        bot_status['in_captcha'] = True

        if active_requests:
            for req_id, req_info in active_requests.items():
                req_info['start_time'] = time.time()
                logger.info(f"⏱️ Reset timeout untuk {req_id}")

        if captcha_timer_task:
            captcha_timer_task.cancel()

        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("Captcha timeout, status direset")
        captcha_timer_task = asyncio.create_task(reset_captcha())

        # Ambil kode captcha
        captcha_code = None
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"🔑 Kode dari teks: {captcha_code}")

        if not captcha_code and message.photo:
            for attempt in range(2):
                try:
                    logger.info(f"📸 OCR percobaan {attempt+1}")
                    captcha_code = await read_number_from_photo_online(message)
                    if captcha_code:
                        logger.info(f"🔑 OCR sukses: {captcha_code}")
                        break
                except Exception as e:
                    logger.error(f"❌ OCR error: {e}")
                if attempt == 0:
                    await asyncio.sleep(2)

        if captcha_code and len(captcha_code) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info("📤 Perintah verify dikirim")
        else:
            logger.error("❌ Gagal dapat kode captcha")
            cleanup_downloaded_photos()

            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "Gagal memproses captcha. Coba lagi."
                )
                try:
                    r.delete(req_id)
                except:
                    pass
                waiting_for_result.pop(f"{req_info['chat_id']}:{req_info['user_id_original']}", None)
                del active_requests[req_id]

            bot_status['in_captcha'] = False
            if captcha_timer_task:
                captcha_timer_task.cancel()
                captcha_timer_task = None

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
                        logger.warning(f"⚠️ Request {req_id} tidak ditemukan")
                        r.lpop('pending_requests')
                        continue

                    req_data = json.loads(req_json)
                    
                    # Ambil data dengan benar
                    chat_id = req_data['chat_id']
                    user_id_original = req_data['user_id']
                    message_id = req_data.get('message_id')
                    command = req_data['command']
                    args = req_data['args']
                    
                    logger.info(f"📋 Memproses request {req_id}")
                    logger.info(f"   • Chat ID: {chat_id}")
                    logger.info(f"   • User ID: {user_id_original}")
                    logger.info(f"   • Message ID: {message_id}")
                    logger.info(f"   • Command: {command}")

                    # Cek apakah user ini sedang menunggu
                    waiting_key = f"{chat_id}:{user_id_original}"
                    if waiting_for_result.get(waiting_key, False):
                        logger.info(f"⏳ User {user_id_original} masih menunggu")
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue

                    # Kirim status "Sedang diproses" (dengan reply jika di grup)
                    status_text = "⏳ Proses request..."
                    msg_id = await send_status_to_user(
                        chat_id, 
                        status_text,
                        reply_to_message_id=message_id if command == '/cekinfo' else None
                    )
                    
                    if not msg_id:
                        logger.error(f"❌ Gagal kirim status")
                        r.lpop('pending_requests')
                        r.delete(req_id)
                        continue

                    # Simpan ke active_requests
                    active_requests[req_id] = {
                        'chat_id': chat_id,
                        'message_id': msg_id,
                        'original_message_id': message_id,
                        'user_id_original': user_id_original,
                        'start_time': now,
                        'command': command,
                        'args': args
                    }
                    
                    logger.info(f"✅ Request {req_id} disimpan")
                    
                    # Kirim ke Bot A
                    cmd = f"{command} {args[0]} {args[1]}"
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Mengirim ke Bot A: {cmd}")

                    sent_requests[req_id] = now
                    waiting_for_result[waiting_key] = True
                    
                    # Hapus dari antrian
                    r.lpop('pending_requests')
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
                logger.info(f"🗑️ Menghapus {key}")
    except Exception as e:
        logger.error(f"❌ Gagal bersihkan Redis: {e}")

    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Login sebagai: {me.first_name}")

        client.add_event_handler(message_handler)
        asyncio.create_task(timeout_checker())
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
