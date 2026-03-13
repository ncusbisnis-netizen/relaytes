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
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# ==================== COUNTRY MAPPING (5 NEGARA) ====================
country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
}

# ==================== KONFIGURASI SCRAPING VHEER ====================
VHEER_URL = "https://vheer.com/app/image-to-text"

# User Agent untuk scraping
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
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

# Cache untuk OCR
ocr_cache = {}

# Konstanta timeout
REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== CLASS OCR VHEER (TANPA API KEY) ====================

class VheerOCRScraper:
    """Class untuk scraping OCR dari Vheer.com tanpa API key"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_request_time = 0
        self.min_delay = 3
        self.upload_count = 0  # Counter untuk tracking
        
    def _wait_for_rate_limit(self):
        """Jeda antar request untuk menghindari block"""
        now = time.time()
        if now - self.last_request_time < self.min_delay:
            time.sleep(self.min_delay - (now - self.last_request_time))
        self.last_request_time = time.time()
    
    def _extract_numbers_from_html(self, html_text: str) -> str:
        """Ekstrak 6 digit angka dari HTML dengan berbagai metode"""
        if not html_text:
            return ''
        
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Metode 1: Cari di elemen result (prioritas tertinggi)
        result_selectors = [
            'div[class*="result"]',
            'div[class*="output"]',
            'div[class*="ocr"]',
            'pre',
            'code',
            'div[class*="text"]',
            'p[class*="result"]',
            'div[class*="content"]',
            'span[class*="result"]'
        ]
        
        for selector in result_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                numbers = re.findall(r'\b\d{6}\b', text)
                if numbers:
                    # Filter angka yang masuk akal (tidak semua digit sama)
                    for num in numbers:
                        if not all(x == num[0] for x in num):
                            logger.info(f"   ✅ Angka valid ditemukan di {selector}: {num}")
                            return num
                    # Kalau semua angka sama, ambil yang pertama
                    logger.info(f"   ✅ Angka ditemukan di {selector}: {numbers[0]}")
                    return numbers[0]
        
        # Metode 2: Cari di semua teks
        all_text = soup.get_text()
        
        # Cari angka 6 digit
        candidates = re.findall(r'\b\d{6}\b', all_text)
        
        if candidates:
            # Filter angka yang masuk akal (tidak 000000, 111111, dll)
            valid_candidates = [c for c in candidates if not all(x == c[0] for x in c)]
            if valid_candidates:
                logger.info(f"   ✅ Angka valid ditemukan di teks: {valid_candidates[0]}")
                return valid_candidates[0]
            
            logger.info(f"   ✅ Angka ditemukan di teks: {candidates[0]}")
            return candidates[0]
        
        # Metode 3: Cari pola 6 digit beruntun (tanpa word boundary)
        all_digits = re.findall(r'\d{6,}', all_text)
        if all_digits:
            longest = max(all_digits, key=len)
            angka = longest[:6]
            # Cek apakah angka masuk akal
            if not all(x == angka[0] for x in angka):
                logger.info(f"   ✅ Angka 6 digit dari string panjang: {angka}")
                return angka
        
        return ''
    
    def _try_get_result_page(self, image_id: str = None) -> str:
        """Coba ambil halaman hasil (kalau ada)"""
        try:
            # Tunggu sebentar biar proses
            time.sleep(3)
            
            # Coba beberapa kemungkinan URL hasil
            result_urls = [
                VHEER_URL,  # Halaman utama
                f"{VHEER_URL}/result",
                "https://vheer.com/api/latest-result",
            ]
            
            if image_id:
                result_urls.insert(0, f"{VHEER_URL}/result/{image_id}")
                result_urls.insert(1, f"https://vheer.com/api/result/{image_id}")
            
            for url in result_urls:
                try:
                    self._wait_for_rate_limit()
                    logger.info(f"📥 Mencoba ambil hasil dari: {url}")
                    
                    resp = self.session.get(url, timeout=15)
                    if resp.status_code == 200:
                        angka = self._extract_numbers_from_html(resp.text)
                        if angka:
                            logger.info(f"   ✅ Angka ditemukan di halaman hasil: {angka}")
                            return angka
                except Exception as e:
                    logger.debug(f"Error ambil hasil dari {url}: {e}")
                    continue
                        
        except Exception as e:
            logger.debug(f"Error ambil hasil: {e}")
        
        return ''
    
    def _try_upload(self, image_path: str) -> tuple:
        """
        Upload gambar ke Vheer.com
        Returns: (success, image_id, result_text)
        """
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg'),
            }
            
            upload_url = VHEER_URL
            self.upload_count += 1
            
            try:
                self._wait_for_rate_limit()
                logger.info(f"📤 Mencoba upload ke: {upload_url} (ke-{self.upload_count})")
                
                resp = self.session.post(
                    upload_url, 
                    files=files,
                    timeout=30,
                    allow_redirects=True
                )
                
                logger.info(f"   Response status: {resp.status_code}")
                
                if resp.status_code == 200:
                    logger.info(f"   ✅ Upload berhasil!")
                    
                    # Ekstrak angka dari response pertama
                    angka = self._extract_numbers_from_html(resp.text)
                    
                    if angka:
                        logger.info(f"   ✅ Angka langsung ditemukan: {angka}")
                        return True, None, angka
                    
                    # Kalau belum dapat, coba ambil image_id dari response
                    logger.info("   ⏳ Angka belum muncul, mencari image_id...")
                    
                    # Cari image_id di response (format JSON dalam HTML)
                    match = re.search(r'"id"\s*:\s*"([a-zA-Z0-9]+)"', resp.text)
                    if not match:
                        match = re.search(r'id[":= ]+["\']?([a-zA-Z0-9]{5,20})["\']?', resp.text)
                    
                    image_id = match.group(1) if match else None
                    if image_id:
                        logger.info(f"   🔑 Image ID ditemukan: {image_id}")
                    
                    # Ambil hasil dari halaman result
                    logger.info("   ⏳ Mencoba ambil dari halaman hasil...")
                    angka = self._try_get_result_page(image_id)
                    
                    if angka:
                        return True, image_id, angka
                    
                    # Kalau masih belum dapat, return HTML mentah
                    logger.warning("   ⚠️ Tidak menemukan angka, return HTML mentah")
                    return True, image_id, resp.text
                
                return False, None, ''
                        
            except requests.exceptions.Timeout:
                logger.error("❌ Timeout upload")
                return False, None, ''
            except Exception as e:
                logger.error(f"❌ Error upload: {e}")
                return False, None, ''
    
    def extract_numbers(self, text: str) -> str:
        """Ekstrak 6 digit angka dengan validasi lebih ketat"""
        if not text:
            return ''
        
        # Jika text adalah HTML, parse dulu
        if text.strip().startswith('<'):
            return self._extract_numbers_from_html(text)
        
        # Cari semua kemungkinan angka 6 digit
        candidates = re.findall(r'\b\d{6}\b', text)
        
        if candidates:
            # Filter angka yang masuk akal (tidak semua digit sama)
            valid_candidates = [c for c in candidates if not all(x == c[0] for x in c)]
            
            if valid_candidates:
                # Prioritaskan angka yang muncul di konteks tertentu
                for angka in valid_candidates:
                    pos = text.find(angka)
                    if pos > 0:
                        context = text[max(0, pos-50):pos+50].lower()
                        keywords = ['kode', 'code', 'captcha', 'verify', 'hasil', 'result', 'ocr']
                        if any(kw in context for kw in keywords):
                            logger.info(f"✅ Angka {angka} ditemukan di konteks")
                            return angka
                
                # Default ambil angka valid pertama
                return valid_candidates[0]
            
            # Kalau semua angka sama (000000, 111111), ambil yang pertama
            logger.warning(f"⚠️ Angka {candidates[0]} terlihat palsu")
            return candidates[0]
        
        # Kalau tidak ada yang exact 6 digit, cari pola lain
        all_digits = re.findall(r'\d+', text)
        for digits in all_digits:
            if len(digits) >= 6:
                angka = digits[:6]
                if not all(x == angka[0] for x in angka):
                    return angka
        
        return ''
    
    def ocr_image(self, image_path: str) -> str:
        """
        OCR gambar menggunakan Vheer.com
        """
        if not os.path.exists(image_path):
            logger.error(f"❌ File tidak ditemukan: {image_path}")
            return ''
        
        logger.info(f"🔍 Memulai OCR Vheer untuk: {os.path.basename(image_path)}")
        
        # Coba upload dengan multiple attempts
        max_attempts = 2
        for attempt in range(max_attempts):
            logger.info(f"📦 Percobaan OCR ke-{attempt+1}/{max_attempts}")
            
            success, _, result_text = self._try_upload(image_path)
            
            if not success:
                if attempt < max_attempts - 1:
                    logger.info(f"⏳ Gagal upload, coba lagi dalam 5 detik...")
                    time.sleep(5)
                continue
            
            # Ekstrak angka
            numbers = self.extract_numbers(result_text) if result_text else ''
            
            if numbers:
                logger.info(f"✅ Angka ditemukan: {numbers}")
                return numbers
            else:
                logger.warning(f"⚠️ Percobaan {attempt+1} gagal mendapatkan angka")
                
            if attempt < max_attempts - 1:
                logger.info(f"⏳ Coba lagi dalam 5 detik...")
                time.sleep(5)
        
        logger.error("❌ Semua percobaan OCR gagal")
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
    text = re.sub(r'\(Private\)', 'Hide information', text)
    text = re.sub(r'Bind \(Private\)', 'Hide information', text)
    text = re.sub(r'Private', 'Hide information', text)
    
    if 'Moonton Unverified' in text:
        parts = text.split('Moonton :', 1)
        if len(parts) > 1:
            text = f"{parts[0]}Moonton : empty."
    
    text = re.sub(r'\(Unverified\)', 'Failed Verification', text)
    text = re.sub(r'Unverified', 'Failed Verification', text)
    
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
    """Format output final"""
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
    data = {
        'chat_id': chat_id,
        'text': text,
    }
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
            logger.info(f"✅ Pesan {message_id} diedit")
        else:
            logger.error(f"❌ Gagal edit: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Exception edit: {e}")

# ==================== TIMEOUT CHECKER ====================
async def timeout_checker():
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

    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # HASIL INFO
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info")
        
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

        try:
            del active_requests[req_id]
            waiting_for_result.pop(user_id, None)
        except:
            pass

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
        logger.info("✅ Verifikasi sukses")

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

    # CAPTCHA
    if (message.photo or 'captcha' in text.lower() or 
        re.search(r'\d{6}', text) or '🔒 Masukkan kode captcha' in text):
        
        logger.warning("🚫 CAPTCHA terdeteksi!")
        bot_status['in_captcha'] = True

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

        captcha_code = None

        # Cek di teks dulu
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"🔑 Kode dari teks: {captcha_code}")

        # Kalau tidak ada di teks, coba OCR Vheer
        if not captcha_code and message.photo:
            for attempt in range(2):  # Coba 2 kali
                try:
                    logger.info(f"📸 Percobaan Vheer OCR ke-{attempt+1}")
                    captcha_code = await read_number_from_photo_vheer(message)
                    if captcha_code:
                        logger.info(f"🔑 Kode dari Vheer OCR: {captcha_code}")
                        
                        # Validasi tambahan: pastikan bukan angka palsu
                        if captcha_code not in ['000000', '111111', '222222', '333333', '444444', 
                                              '555555', '666666', '777777', '888888', '999999', '123456']:
                            await asyncio.sleep(2)
                            break
                        else:
                            logger.warning(f"⚠️ Kode {captcha_code} terlihat palsu, coba lagi...")
                            captcha_code = None
                            
                except Exception as e:
                    logger.error(f"❌ Error: {e}")
                
                # Jeda lebih lama antar percobaan
                if attempt < 1:
                    await asyncio.sleep(8)

        if captcha_code and len(captcha_code) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info("📤 Perintah verify dikirim")
        else:
            logger.error("❌ Gagal mendapatkan kode captcha")
            cleanup_downloaded_photos()

            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "Gagal memproses request. Coba lagi."
                )
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                except:
                    pass
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

                    msg_id = await send_status_to_user(
                        user_id, 
                        "Proses request...", 
                        reply_to_message_id=reply_to_message_id
                    )
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
