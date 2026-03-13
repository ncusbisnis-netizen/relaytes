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
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urljoin

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
# OCR_SPACE_API_KEY TIDAK DIGUNAKAN LAGI!
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# ==================== COUNTRY MAPPING (5 NEGARA) ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
}

# ==================== KONFIGURASI SCRAPING ====================
VHEER_URL = "https://vheer.com/app/image-to-text"
VHEER_API_URLS = [
    "https://vheer.com/api/upload",
    "https://vheer.com/api/image-to-text/upload",
    "https://vheer.com/api/ocr/upload",
]
VHEER_RESULT_URLS = [
    "https://vheer.com/api/result/{id}",
    "https://vheer.com/api/image-to-text/result/{id}",
    "https://vheer.com/api/ocr/result/{id}",
]

# Cache untuk OCR
ocr_cache = {}

# User Agent untuk scraping
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'id,en;q=0.9',
    'Origin': 'https://vheer.com',
    'Referer': 'https://vheer.com/app/image-to-text',
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

# Konstanta timeout
REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== FUNGSI OCR BARU DENGAN SCRAPING VHEER ====================

class VheerOCRScraper:
    """Class untuk scraping OCR dari Vheer.com tanpa API key"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_request_time = 0
        self.min_delay = 2  # minimal jeda antar request (detik)
        
    def _wait_for_rate_limit(self):
        """Jeda antar request untuk menghindari block"""
        now = time.time()
        if now - self.last_request_time < self.min_delay:
            time.sleep(self.min_delay - (now - self.last_request_time))
        self.last_request_time = time.time()
    
    def _get_csrf_token(self) -> str:
        """Ambil CSRF token dari halaman utama (jika ada)"""
        try:
            self._wait_for_rate_limit()
            response = self.session.get(VHEER_URL, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Cari meta tag csrf
            meta = soup.find('meta', {'name': 'csrf-token'})
            if meta:
                return meta.get('content', '')
            
            # Cari input hidden dengan name _token
            token_input = soup.find('input', {'name': '_token'})
            if token_input:
                return token_input.get('value', '')
                
        except Exception as e:
            logger.debug(f"Gagal ambil CSRF token: {e}")
        
        return ''
    
    def _try_upload(self, image_path: str, csrf_token: str = '') -> tuple:
        """
        Coba upload ke berbagai endpoint
        Returns: (success, image_id, response_text)
        """
        with open(image_path, 'rb') as f:
            files = {
                'image': (os.path.basename(image_path), f, 'image/jpeg'),
                'file': (os.path.basename(image_path), f, 'image/jpeg'),
            }
            
            data = {}
            if csrf_token:
                data['_token'] = csrf_token
            
            # Coba berbagai endpoint upload
            for upload_url in VHEER_API_URLS:
                try:
                    self._wait_for_rate_limit()
                    logger.info(f"📤 Mencoba upload ke: {upload_url}")
                    
                    # Coba dengan key 'image'
                    resp = self.session.post(upload_url, files={'image': files['image']}, data=data, timeout=15)
                    
                    if resp.status_code not in [200, 201]:
                        # Coba dengan key 'file'
                        resp = self.session.post(upload_url, files={'file': files['file']}, data=data, timeout=15)
                    
                    if resp.status_code in [200, 201]:
                        logger.info(f"✅ Upload berhasil ke {upload_url}")
                        
                        # Parse response
                        try:
                            result = resp.json()
                            # Cari ID di berbagai kemungkinan key
                            image_id = (result.get('id') or 
                                      result.get('file_id') or 
                                      result.get('image_id') or 
                                      result.get('data', {}).get('id'))
                            
                            if image_id:
                                return True, str(image_id), resp.text
                        except:
                            # Mungkin response bukan JSON
                            pass
                            
                except Exception as e:
                    logger.debug(f"Gagal upload ke {upload_url}: {e}")
                    continue
        
        return False, None, ''
    
    def _try_get_result(self, image_id: str, max_retries: int = 5) -> str:
        """
        Ambil hasil OCR dengan berbagai endpoint
        """
        for attempt in range(max_retries):
            for result_pattern in VHEER_RESULT_URLS:
                try:
                    result_url = result_pattern.format(id=image_id)
                    self._wait_for_rate_limit()
                    
                    logger.info(f"📥 Mencoba ambil hasil dari: {result_url}")
                    resp = self.session.get(result_url, timeout=10)
                    
                    if resp.status_code == 200:
                        # Coba parse JSON
                        try:
                            data = resp.json()
                            # Cari teks di berbagai kemungkinan key
                            text = (data.get('text') or 
                                   data.get('result') or 
                                   data.get('data', {}).get('text') or
                                   data.get('parsedText') or
                                   data.get('ParsedText'))
                            if text:
                                return str(text)
                        except:
                            # Mungkin response plain text
                            if resp.text and len(resp.text) > 0:
                                return resp.text
                                
                except Exception as e:
                    logger.debug(f"Gagal ambil hasil dari {result_url}: {e}")
            
            # Tunggu sebelum retry
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # exponential backoff: 1, 2, 4 detik
                logger.info(f"⏳ Hasil belum siap, tunggu {wait_time} detik...")
                time.sleep(wait_time)
        
        return ''
    
    def extract_numbers(self, text: str) -> str:
        """Ekstrak 6 digit angka dari teks"""
        if not text:
            return ''
        
        # Hapus semua non-digit
        digits = re.sub(r'[^0-9]', '', text)
        
        # Cari 6 digit berurutan
        match = re.search(r'(\d{6})', digits)
        if match:
            return match.group(1)
        
        # Kalau tidak ada 6 digit, ambil 6 digit pertama
        if len(digits) >= 6:
            return digits[:6]
        
        return ''
    
    def ocr_image(self, image_path: str) -> str:
        """
        Main function: OCR gambar menggunakan Vheer.com
        
        Args:
            image_path: path ke file gambar
            
        Returns:
            6 digit angka atau string kosong
        """
        # Cek file exists
        if not os.path.exists(image_path):
            logger.error(f"❌ File tidak ditemukan: {image_path}")
            return ''
        
        logger.info(f"🔍 Memulai OCR Vheer untuk: {image_path}")
        
        # 1. Dapatkan CSRF token
        csrf_token = self._get_csrf_token()
        if csrf_token:
            logger.info(f"✅ CSRF token ditemukan")
        
        # 2. Upload gambar
        success, image_id, _ = self._try_upload(image_path, csrf_token)
        if not success or not image_id:
            logger.error("❌ Gagal upload gambar")
            return ''
        
        logger.info(f"✅ Image ID: {image_id}")
        
        # 3. Tunggu proses (kasih waktu)
        time.sleep(3)
        
        # 4. Ambil hasil
        result_text = self._try_get_result(image_id)
        
        if result_text:
            logger.info(f"✅ Hasil mentah: {result_text[:100]}...")
            
            # Ekstrak angka
            numbers = self.extract_numbers(result_text)
            if numbers:
                logger.info(f"✅ Angka ditemukan: {numbers}")
                return numbers
            else:
                logger.warning(f"⚠️ Tidak ada angka dalam hasil: {result_text}")
        else:
            logger.error("❌ Gagal mendapatkan hasil OCR")
        
        return ''

# Buat instance global scraper
vheer_scraper = VheerOCRScraper()

async def read_number_from_photo_vheer(message):
    """
    OCR menggunakan Vheer.com (scraping, tanpa API key)
    """
    try:
        logger.info("📸 Downloading captcha photo untuk Vheer OCR...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        # Panggil scraper (sync function, jalankan di thread pool)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            vheer_scraper.ocr_image, 
            photo_path
        )
        
        if result:
            logger.info(f"✅ Vheer OCR berhasil: {result}")
            return result
        else:
            logger.warning("⚠️ Vheer OCR gagal mendapatkan angka")
            return None
            
    except Exception as e:
        logger.error(f"❌ Vheer OCR error: {e}")
        return None

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
                        # Format dengan benar - pastikan tidak double dot
                        if ':' in main_line:
                            parts = main_line.split(':', 1)
                            label = parts[0].strip()
                            # Pastikan label hanya "Moonton" sekali
                            if label.count('Moonton') > 1:
                                label = 'Moonton'
                            # Gunakan "empty." tanpa tambahan titik
                            bind_info.append(f"• {label}: empty.")
                        else:
                            bind_info.append(f"• Moonton: empty.")
                    else:
                        # Tidak empty, proses normal
                        main_line = clean_bind_text(main_line)
                        
                        # Pastikan formatnya "Moonton: value"
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
                
                # Pastikan formatnya "Keyword: value"
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
    """Kirim pesan status ke user melalui Bot B (bisa sebagai reply)"""
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
        logger.info(f"📤 Mengirim status ke user {chat_id}" + (f" (reply ke {reply_to_message_id})" if reply_to_message_id else ""))
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

    # ========== 1. HASIL INFO (format dengan garis) ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info dari Bot A")
        
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif, hasil diabaikan")
            return

        req_id, req_info = next(iter(active_requests.items()))
        user_id = req_info['chat_id']
        message_id = req_info['message_id']

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
        except Exception as e:
            logger.error(f"❌ Gagal hapus active_requests: {e}")

        # Hapus dari Redis
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id:
                r.lpop('pending_requests')
            r.delete(req_id)
        except Exception as e:
            logger.error(f"❌ Gagal hapus Redis: {e}")

        cleanup_downloaded_photos()
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

        # Reset timeout untuk request yang sedang aktif
        if active_requests:
            for req_id, req_info in active_requests.items():
                req_info['start_time'] = time.time()

        if captcha_timer_task:
            captcha_timer_task.cancel()

        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("Captcha timeout, status direset")
        captcha_timer_task = asyncio.create_task(reset_captcha())

        # Ambil kode captcha
        captcha_code = None

        # Cek di teks terlebih dahulu
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"🔑 Kode captcha dari teks: {captcha_code}")

        # Jika tidak ada di teks dan ada foto, coba OCR Vheer (TANPA API KEY!)
        if not captcha_code and message.photo:
            for attempt in range(3):  # Coba maksimal 3 kali
                try:
                    logger.info(f"📸 Percobaan Vheer OCR ke-{attempt+1}")
                    captcha_code = await read_number_from_photo_vheer(message)
                    if captcha_code:
                        logger.info(f"🔑 Kode captcha dari Vheer OCR (percobaan {attempt+1}): {captcha_code}")
                        break
                    else:
                        logger.warning(f"Vheer OCR percobaan {attempt+1} gagal")
                except Exception as e:
                    logger.error(f"❌ Vheer OCR percobaan {attempt+1} error: {e}")
                
                if attempt < 2:  # Jeda sebelum retry
                    await asyncio.sleep(3)

        if captcha_code and len(captcha_code) == 6:
            # Kirim verify ke Bot A
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info("📤 Perintah verify dikirim")
        else:
            logger.error("❌ Gagal mendapatkan kode captcha setelah 3 percobaan Vheer OCR")
            cleanup_downloaded_photos()

            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "Gagal memproses request. Coba lagi."
                )
                # Hapus dari Redis
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                except Exception as e:
                    logger.error(f"❌ Gagal hapus Redis: {e}")
                
                waiting_for_result.pop(req_info['chat_id'], None)
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
                    reply_to_message_id = req_data.get('reply_to_message_id')

                    if waiting_for_result.get(user_id, False):
                        logger.info(f"⏳ User {user_id} masih menunggu, pindahkan ke belakang")
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue

                    status_text = "Proses request..."
                    msg_id = await send_status_to_user(user_id, status_text, reply_to_message_id=reply_to_message_id)
                    if not msg_id:
                        logger.error(f"❌ Gagal mengirim status ke user {user_id}")
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
    logger.info("🚀 Memulai userbot dengan Vheer OCR (TANPA API KEY!)...")

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

        client.add_event_handler(message_handler)
        asyncio.create_task(timeout_checker())
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
