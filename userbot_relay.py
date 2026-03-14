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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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

# ==================== CLASS OCR SELENIUM ====================

class VheerOCRSelenium:
    """OCR Vheer menggunakan Selenium (browser sungguhan)"""
    
    def __init__(self):
        self.options = Options()
        self.options.add_argument('--headless')  # Jalan di background
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        
        # Set binary location untuk Heroku
        firefox_bin = os.environ.get('FIREFOX_BIN', '/app/.apt/usr/bin/firefox')
        if os.path.exists(firefox_bin):
            self.options.binary_location = firefox_bin
            
    def _extract_valid_angka(self, text: str) -> str:
        """Ekstrak angka 6 digit yang valid dari teks"""
        if not text:
            return ''
        
        # Cari semua angka 6 digit
        candidates = re.findall(r'\b\d{6}\b', text)
        
        # Daftar angka palsu yang harus dihindari
        fake_numbers = ['000000', '111111', '222222', '333333', '444444',
                       '555555', '666666', '777777', '888888', '999999', '123456']
        
        for angka in candidates:
            if angka not in fake_numbers:
                return angka
        
        # Kalau semua palsu, ambil yang pertama
        return candidates[0] if candidates else ''
    
    def ocr_image(self, image_path: str) -> str:
        """
        Upload gambar ke Vheer.com dan ambil hasil OCR
        """
        driver = None
        try:
            logger.info("🚀 Memulai Selenium driver...")
            driver = webdriver.Firefox(options=self.options)
            driver.set_page_load_timeout(30)
            
            # Buka halaman
            logger.info("📡 Membuka halaman Vheer...")
            driver.get("https://vheer.com/app/image-to-text")
            
            # Tunggu halaman load
            time.sleep(3)
            
            # Cari input file
            logger.info("🔍 Mencari input file...")
            file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            
            # Upload file
            abs_path = os.path.abspath(image_path)
            logger.info(f"📤 Upload file: {abs_path}")
            file_input.send_keys(abs_path)
            
            # Tunggu upload
            time.sleep(3)
            
            # Cari dan klik tombol proses
            logger.info("🔍 Mencari tombol Image to Text...")
            try:
                # Coba berbagai selector
                tombol = None
                selectors = [
                    "//button[contains(text(), 'Image to Text')]",
                    "//button[contains(@class, 'bg-amber')]",
                    "//button[contains(@class, 'violet')]",
                    "button[type='submit']"
                ]
                
                for selector in selectors:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        tombol = elements[0]
                        break
                
                if tombol:
                    driver.execute_script("arguments[0].click();", tombol)
                    logger.info("✅ Tombol diklik")
                else:
                    logger.warning("⚠️ Tombol tidak ditemukan")
                    
            except Exception as e:
                logger.warning(f"⚠️ Gagal klik tombol: {e}")
            
            # TUNGGU HASIL (paling penting!)
            logger.info("⏳ Menunggu hasil OCR 15 detik...")
            time.sleep(15)
            
            # Ambil semua teks dari halaman
            logger.info("🔍 Mengambil teks dari halaman...")
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Cari angka valid
            angka = self._extract_valid_angka(page_text)
            
            if angka:
                logger.info(f"✅ ANGKA DITEMUKAN: {angka}")
                return angka
            
            # Kalau tidak ketemu, coba screenshot untuk debug
            screenshot_path = "/tmp/vheer_screenshot.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"📸 Screenshot disimpan: {screenshot_path}")
            
            logger.warning("⚠️ Tidak ada angka 6 digit dalam response")
            return ''
            
        except Exception as e:
            logger.error(f"❌ Error Selenium: {e}")
            return ''
            
        finally:
            if driver:
                driver.quit()
                logger.info("🚪 Browser ditutup")

# Buat instance
vheer_selenium = VheerOCRSelenium()

async def read_captcha(message):
    """Baca captcha dari foto menggunakan Selenium"""
    try:
        path = await message.download_media()
        downloaded_photos.append(path)
        logger.info(f"📸 Foto didownload: {path}")
        
        # Jalankan Selenium di thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, vheer_selenium.ocr_image, path)
        
        return result if result else None
        
    except Exception as e:
        logger.error(f"❌ Error read_captcha: {e}")
        return None

# ==================== FUNGSI BANTUAN ====================
def clean_bind_text(text):
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
        response = requests.post(url, headers=headers, json=body, timeout=30)
        if response.status_code not in [200, 201]:
            return {'status': False, 'message': f'HTTP {response.status_code}'}
        result = response.json()
        if not result or 'data' not in result:
            return {'status': False, 'message': 'Invalid response'}
        data = result['data']
        username = data.get('username', 'Unknown').replace('+', ' ')
        country = data.get('countryOrigin', 'ID').upper()
        region = country_mapping.get(country, f'🌍 {country}')
        return {'status': True, 'username': username, 'region': region}
    except Exception as e:
        return {'status': False, 'message': str(e)}

def cleanup_downloaded_photos():
    global downloaded_photos
    for path in downloaded_photos[:]:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"🗑️ Hapus: {path}")
            downloaded_photos.remove(path)
        except:
            pass

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
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

# ==================== FUNGSI BOT ====================
async def send_status(chat_id, text, reply_to=None, markup=None):
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text}
    if reply_to:
        data['reply_to_message_id'] = reply_to
    if markup:
        data['reply_markup'] = json.dumps(markup)
    try:
        resp = requests.post(url, json=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()['result']['message_id']
    except:
        pass
    return None

async def edit_status(chat_id, msg_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {'chat_id': chat_id, 'message_id': msg_id, 'text': text}
    if markup:
        data['reply_markup'] = json.dumps(markup)
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

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
                await edit_status(req_data['chat_id'], req_data['message_id'], 
                                "Request timeout. Silakan coba lagi.")
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                except:
                    pass
                waiting_for_result.pop(req_data['chat_id'], None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)
        await asyncio.sleep(1)

# ==================== HANDLER ====================
@events.register(events.NewMessage)
async def message_handler(event):
    global captcha_timer_task, bot_status

    msg = event.message
    if msg.chat_id != 7240340418 and msg.sender_id != 7240340418:
        return

    text = msg.text or msg.message or ''
    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # HASIL INFO
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        if not active_requests:
            return
        req_id, req_info = next(iter(active_requests.items()))
        
        uid = re.search(r'ID:?\s*(\d+)', text)
        sid = re.search(r'Server:?\s*(\d+)', text)
        android = re.search(r'Android:?\s*(\d+)', text)
        ios = re.search(r'iOS:?\s*(\d+)', text)
        
        uid = uid.group(1) if uid else 'Unknown'
        sid = sid.group(1) if sid else 'Unknown'
        android = android.group(1) if android else '0'
        ios = ios.group(1) if ios else '0'
        
        gopay = validate_mlbb_gopay_sync(uid, sid)
        nickname = gopay['username'] if gopay['status'] else 'Tidak diketahui'
        region = gopay['region'] if gopay['status'] else '🌍 Tidak diketahui'
        
        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)
        await edit_status(req_info['chat_id'], req_info['message_id'], output, markup)
        
        try:
            del active_requests[req_id]
            waiting_for_result.pop(req_info['chat_id'], None)
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
        if captcha_timer_task:
            captcha_timer_task.cancel()
        bot_status['in_captcha'] = False
        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            cmd = f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}"
            await client.send_message(BOT_A_USERNAME, cmd)
            req_info['start_time'] = time.time()
        return

    # CAPTCHA
    if (msg.photo or 'captcha' in text.lower() or '🔒 Masukkan kode captcha' in text):
        logger.warning("🚫 CAPTCHA DETECTED!")
        bot_status['in_captcha'] = True
        
        if active_requests:
            for r in active_requests.values():
                r['start_time'] = time.time()
        
        if captcha_timer_task:
            captcha_timer_task.cancel()
        
        async def reset():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("⏰ Captcha timeout")
        captcha_timer_task = asyncio.create_task(reset())
        
        # Cek kode di teks dulu
        kode = None
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            kode = ''.join(digits[:6])
            logger.info(f"🔑 Kode dari teks: {kode}")
        
        # OCR dengan Selenium
        if not kode and msg.photo:
            logger.info("📸 Memulai OCR dengan Selenium...")
            kode = await read_captcha(msg)
            if kode:
                logger.info(f"✅ Kode dari Selenium: {kode}")
                await asyncio.sleep(2)
        
        if kode and len(kode) == 6:
            await client.send_message(BOT_A_USERNAME, f"/verify {kode}")
            logger.info("📤 Perintah verify dikirim")
        else:
            logger.error("❌ Gagal mendapatkan kode captcha")
            cleanup_downloaded_photos()
            if active_requests:
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status(req_info['chat_id'], req_info['message_id'],
                                "Gagal memproses request. Coba lagi.")
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

# ==================== QUEUE ====================
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
                    reply_id = req_data.get('reply_to_message_id')
                    
                    if waiting_for_result.get(user_id):
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue
                    
                    msg_id = await send_status(user_id, "Proses request...", reply_id)
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
            logger.error(f"❌ Error queue: {e}")
        await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot dengan Selenium OCR...")
    
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
        asyncio.create_task(timeout_checker())
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
