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
import uuid

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

# Auto Redeem Config
AUTO_REDEEM_ENABLED = os.environ.get('AUTO_REDEEM_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_CHANNEL = os.environ.get('AUTO_REDEEM_CHANNEL', 'redeemtest')
REDEEM_DELAY = int(os.environ.get('REDEEM_DELAY', '5'))

# ==================== COUNTRY MAPPING SEDERHANA ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
    'VN': '🇻🇳 Vietnam',
    'US': '🇺🇸 United States',
    'GB': '🇬🇧 United Kingdom',
    'JP': '🇯🇵 Japan',
    'KR': '🇰🇷 South Korea',
    'CN': '🇨🇳 China',
    'IN': '🇮🇳 India',
    'BR': '🇧🇷 Brazil',
    'AU': '🇦🇺 Australia',
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
sent_requests = {}
waiting_for_result = {}
downloaded_photos = []
active_requests = {}
captcha_timer_task = None

REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== AUTO REDEEM CLASS ====================
class AutoRedeemManager:
    def __init__(self):
        self.redeemed_codes = set()
        self.failed_codes = set()
        self.last_message_ids = set()
        
    def add_redeemed(self, code):
        self.redeemed_codes.add(code)
        logger.info(f"✅ Kode {code} redeemed")
    
    def add_failed(self, code):
        self.failed_codes.add(code)
        logger.info(f"❌ Kode {code} failed")
    
    def is_redeemed(self, code):
        clean = code.replace('-', '').replace('VCR', '')
        for r in self.redeemed_codes:
            if clean in r or r in clean:
                return True
        for f in self.failed_codes:
            if clean in f or f in clean:
                return True
        return False
    
    def is_processed(self, msg_id):
        return msg_id in self.last_message_ids
    
    def add_processed(self, msg_id):
        self.last_message_ids.add(msg_id)
        if len(self.last_message_ids) > 500:
            self.last_message_ids = set(list(self.last_message_ids)[-200:])
    
    def save(self):
        try:
            data = {
                'redeemed': list(self.redeemed_codes),
                'failed': list(self.failed_codes),
                'last_msgs': list(self.last_message_ids)
            }
            r.set('auto_redeem', json.dumps(data))
            logger.info("💾 Auto redeem data saved")
        except Exception as e:
            logger.error(f"❌ Save error: {e}")
    
    def load(self):
        try:
            data = r.get('auto_redeem')
            if data:
                d = json.loads(data)
                self.redeemed_codes = set(d.get('redeemed', []))
                self.failed_codes = set(d.get('failed', []))
                self.last_message_ids = set(d.get('last_msgs', []))
                logger.info(f"📂 Loaded: {len(self.redeemed_codes)} redeemed codes")
        except Exception as e:
            logger.error(f"❌ Load error: {e}")

auto_redeem = AutoRedeemManager()

# ==================== FUNGSI BANTUAN ====================
def get_region(country_code):
    """Dapatkan region dari kode negara"""
    country_code = country_code.upper()
    return country_mapping.get(country_code, f"🌍 {country_code}")

def clean_bind_text(text):
    """Bersihkan text bind info"""
    if 'Private' in text:
        text = re.sub(r'Bind\s*\(Private\)', 'Hide information', text)
        text = re.sub(r'\(Private\)', 'Hide information', text)
        text = re.sub(r'\bPrivate\b', 'Hide information', text)
    
    text = re.sub(r'\s*\(Unverified\)', '', text)
    
    if 'Moonton Unverified' in text:
        if 'Moonton :' in text or 'Moonton:' in text:
            text = re.sub(r'Moonton\s*:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
        else:
            text = re.sub(r'Moonton\s+Unverified', 'Moonton: empty.', text)
    
    if 'empty' in text.lower() and text.count('Moonton') > 1:
        parts = text.split('empty', 1)
        before_empty = parts[0]
        if 'Moonton' in before_empty:
            moonton_parts = before_empty.split('Moonton')
            if len(moonton_parts) > 1:
                text = f"Moonton: empty.{parts[1] if len(parts) > 1 else ''}"
    
    text = re.sub(r'empty\.\.', 'empty.', text)
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
        region = get_region(country)
        
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
    try:
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)

        with open(photo_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")

        base64_data = f"data:image/jpeg;base64,{base64_image}"

        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers = {
            "accept": "text/x-component",
            "user-agent": "Mozilla/5.0",
            "referer": "https://vheer.com/app/image-to-text",
            "next-action": "99625e5ddd7496b07a3d1bef68618b3c0dea0807",
            "next-router-state-tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22app%22%2C%7B%22children%22%3A%5B%22image-to-text%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Fapp%2Fimage-to-text%22%2C%22refresh%22%5D%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D",
            "content-type": f"multipart/form-data; boundary={boundary}"
        }

        def build_form():
            parts = []
            
            def add_field(name, value):
                parts.append(f"--{boundary}")
                parts.append(f'Content-Disposition: form-data; name="{name}"\r\n')
                parts.append(value)

            add_field("1_imageBase64", base64_data)
            add_field("1_languageIndex", "ENG")
            add_field("0", f'["$K1","{uuid.uuid4().hex[:10]}"]')

            parts.append(f"--{boundary}--\r\n")
            return "\r\n".join(parts)

        body = build_form()

        response = requests.post(
            "https://vheer.com/app/image-to-text",
            data=body.encode(),
            headers=headers,
            timeout=60
        )

        if response.status_code == 200:
            try:
                raw = response.text.split("\n")[1]
                parsed = json.loads(raw[2:])

                text = parsed.get("text", "")
                text = re.sub(r'[^0-9]', '', text)

                match = re.search(r'(\d{6})', text)
                if match:
                    return match.group(1)

            except Exception as e:
                logger.error(f"❌ Parse error: {e}")

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
    """Kirim pesan status ke user melalui Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id:
        data['reply_to_message_id'] = reply_to_message_id
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        logger.info(f"📤 Mengirim status ke user {chat_id}")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            msg_id = response.json()['result']['message_id']
            logger.info(f"✅ Status terkirim, message_id: {msg_id}")
            return msg_id
        else:
            logger.error(f"❌ Gagal kirim status: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Exception kirim status: {e}")
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    """Edit pesan yang sudah dikirim ke user"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Pesan {message_id} berhasil diedit")
    except Exception as e:
        logger.error(f"❌ Exception saat edit pesan: {e}")

# ==================== AUTO REDEEM FUNCTIONS ====================
def extract_vcr_codes(text):
    """Ekstrak semua kode VCR dari teks"""
    if not text:
        return []
    
    codes = []
    patterns = [
        r'(VCR-[A-Z0-9]{6,12})',
        r'(VCR[A-Z0-9]{6,12})',
        r'(VCR\s+[A-Z0-9]{6,12})',
        r'([Vv][Cc][Rr][-\s]?[A-Z0-9]{6,12})',
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        all_matches.extend(matches)
    
    seen = set()
    for match in all_matches:
        code = str(match).upper().strip()
        
        if 'VCR' in code:
            if '-' in code:
                parts = code.split('-')
                if len(parts) >= 2:
                    code = f"VCR-{parts[-1]}"
            else:
                vcr_pos = code.find('VCR')
                if vcr_pos != -1:
                    after_vcr = code[vcr_pos+3:]
                    after_vcr = re.sub(r'[^A-Z0-9]', '', after_vcr)
                    if after_vcr:
                        code = f"VCR-{after_vcr}"
        
        clean = code.replace('-', '').replace('VCR', '')
        if len(clean) >= 4 and code not in seen:
            seen.add(code)
            codes.append(code)
    
    return codes

def has_vcr(text):
    """Cek apakah ada VCR di teks"""
    return bool(re.search(r'[Vv][Cc][Rr]', text))

async def send_redeem_command(code):
    """Kirim command redeem ke bot"""
    try:
        cmd = f"/redeem {code}"
        logger.info(f"🔄 Sending: {cmd}")
        await client.send_message(BOT_A_USERNAME, cmd)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        return False

async def process_voucher_codes(codes, message_id):
    """Proses semua kode voucher yang ditemukan"""
    global auto_redeem
    
    new_codes = []
    for code in codes:
        if not auto_redeem.is_redeemed(code):
            new_codes.append(code)
    
    if not new_codes:
        return
    
    logger.info(f"🎯 Processing {len(new_codes)} codes: {new_codes}")
    
    for i, code in enumerate(new_codes, 1):
        if i > 1:
            await asyncio.sleep(REDEEM_DELAY)
        
        success = await send_redeem_command(code)
        
        if success:
            auto_redeem.add_redeemed(code)
        else:
            auto_redeem.add_failed(code)
    
    auto_redeem.save()

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
                logger.warning(f"⏰ Timeout untuk request {req_id}")
                await edit_status_message(
                    req_data['chat_id'],
                    req_data['message_id'],
                    "Request timeout. Silakan coba lagi."
                )
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                except Exception as e:
                    logger.error(f"❌ Gagal hapus Redis: {e}")
                waiting_for_result.pop(req_data['chat_id'], None)
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

    # Hanya pesan dari Bot A yang diproses
    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # HASIL INFO
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        if not active_requests:
            return

        req_id, req_info = next(iter(active_requests.items()))
        user_id = req_info['chat_id']
        message_id = req_info['message_id']

        id_match = re.search(r'ID:?\s*(\d+)', text)
        server_match = re.search(r'Server:?\s*(\d+)', text)
        android_match = re.search(r'Android:?\s*(\d+)', text)
        ios_match = re.search(r'iOS:?\s*(\d+)', text)

        uid = id_match.group(1) if id_match else 'Unknown'
        sid = server_match.group(1) if server_match else 'Unknown'
        android = android_match.group(1) if android_match else '0'
        ios = ios_match.group(1) if ios_match else '0'

        gopay = validate_mlbb_gopay_sync(uid, sid)
        if gopay['status']:
            nickname = gopay['username']
            region = gopay['region']
        else:
            nickname = 'Tidak diketahui'
            region = '🌍 Tidak diketahui'

        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)
        await edit_status_message(user_id, message_id, output, markup)

        del active_requests[req_id]
        waiting_for_result.pop(user_id, None)
        
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id:
                r.lpop('pending_requests')
            r.delete(req_id)
        except:
            pass

        cleanup_downloaded_photos()
        return

    # VERIFIKASI SUKSES
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        bot_status['in_captcha'] = False

        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            cmd = f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}"
            await client.send_message(BOT_A_USERNAME, cmd)
            req_info['start_time'] = time.time()
        return

    # CAPTCHA
    if (message.photo or 'captcha' in text.lower() or re.search(r'\d{6}', text)):
        bot_status['in_captcha'] = True

        if active_requests:
            for req_id, req_info in active_requests.items():
                req_info['start_time'] = time.time()

        if captcha_timer_task:
            captcha_timer_task.cancel()

        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
        captcha_timer_task = asyncio.create_task(reset_captcha())

        captcha_code = None
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])

        if not captcha_code and message.photo:
            for attempt in range(2):
                try:
                    captcha_code = await read_number_from_photo_online(message)
                    if captcha_code:
                        break
                except:
                    pass
                if attempt == 0:
                    await asyncio.sleep(2)

        if captcha_code and len(captcha_code) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
        else:
            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(req_info['chat_id'], req_info['message_id'], "Gagal memproses request. Coba lagi.")
                waiting_for_result.pop(req_info['chat_id'], None)
                del active_requests[req_id]
            bot_status['in_captcha'] = False

# ==================== AUTO REDEEM HANDLER ====================
@events.register(events.NewMessage)
async def auto_redeem_handler(event):
    """Handler auto redeem dari channel"""
    global auto_redeem
    
    if not AUTO_REDEEM_ENABLED:
        return
    
    message = event.message
    chat = await event.get_chat()
    
    chat_username = getattr(chat, 'username', None)
    chat_title = getattr(chat, 'title', '')
    
    is_target = (
        chat_username == AUTO_REDEEM_CHANNEL or
        AUTO_REDEEM_CHANNEL in chat_title.lower()
    )
    
    if not is_target:
        return
    
    if auto_redeem.is_processed(message.id):
        return
    
    text = message.text or message.message or ''
    if not text:
        return
    
    logger.info(f"📨 New message from {chat_title}")
    
    if not has_vcr(text):
        return
    
    logger.info("🎯 VCR detected!")
    
    codes = extract_vcr_codes(text)
    if not codes:
        return
    
    auto_redeem.add_processed(message.id)
    await process_voucher_codes(codes, message.id)

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

                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2)
                        continue

                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests')
                        continue

                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                    reply_to_message_id = req_data.get('reply_to_message_id')

                    if waiting_for_result.get(user_id, False):
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue

                    msg_id = await send_status_to_user(user_id, "Proses request...", reply_to_message_id)
                    if not msg_id:
                        r.lpop('pending_requests')
                        r.delete(req_id)
                        continue

                    active_requests[req_id] = {
                        'chat_id': user_id,
                        'message_id': msg_id,
                        'start_time': now,
                        'command': req_data['command'],
                        'args': req_data['args']
                    }

                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    await client.send_message(BOT_A_USERNAME, cmd)

                    sent_requests[req_id] = now
                    waiting_for_result[user_id] = True
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error di process_queue: {e}")
        await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot...")
    logger.info("=" * 50)
    
    # Load auto redeem data
    auto_redeem.load()
    
    logger.info(f"📊 Auto Redeem: {'✅ ACTIVE' if AUTO_REDEEM_ENABLED else '❌ DISABLED'}")
    logger.info(f"📊 Target Channel: @{AUTO_REDEEM_CHANNEL}")
    logger.info(f"📊 Redeem Delay: {REDEEM_DELAY} seconds")
    logger.info(f"📊 Total Redeemed: {len(auto_redeem.redeemed_codes)} codes")
    logger.info("=" * 50)

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
        logger.info(f"🟢 Memantau channel @{AUTO_REDEEM_CHANNEL}...")

        # Daftarkan event handler
        client.add_event_handler(message_handler)
        client.add_event_handler(auto_redeem_handler)

        # Jalankan timeout checker
        asyncio.create_task(timeout_checker())

        # Jalankan pemrosesan antrian
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
