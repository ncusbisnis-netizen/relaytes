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
from PIL import Image
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

# ==================== FUNGSI OCR UNTUK CAPTCHA GAMBAR ====================

async def solve_captcha_simple(message):
    """
    OCR sederhana khusus angka 6 digit dari gambar
    """
    try:
        logger.info("📸 OCR: Downloading captcha image...")
        
        # Download foto
        photo_path = await message.download()
        logger.info(f"✅ Image downloaded: {photo_path}")
        
        # Buka dengan PIL
        img = Image.open(photo_path)
        
        # Convert ke grayscale
        img = img.convert('L')
        
        # Threshold sederhana (angka putih, background gelap)
        threshold = 200
        img = img.point(lambda p: p > threshold and 255)
        
        # Simpan sementara
        temp_path = f"/tmp/captcha_{int(time.time())}.png"
        img.save(temp_path)
        
        # OCR dengan pytesseract (khusus angka)
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(temp_path, config=custom_config)
        
        # Bersihkan file
        os.remove(photo_path)
        os.remove(temp_path)
        
        # Ambil 6 digit
        text = re.sub(r'[^0-9]', '', text)
        match = re.search(r'(\d{6})', text)
        
        if match:
            code = match.group(1)
            logger.info(f"✅ OCR BERHASIL: {code}")
            return code
        else:
            logger.warning(f"❌ OCR GAGAL: {text}")
            return None
        
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

async def solve_captcha_fallback(img):
    """
    Fallback OCR dengan preprocessing berbeda
    """
    try:
        logger.info("🔄 Mencoba metode OCR alternatif...")
        
        # Convert PIL ke OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Metode alternatif
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 11, 2)
        
        # Resize untuk memperbesar
        scaled = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        temp_path = f"/tmp/captcha_fallback_{int(time.time())}.png"
        cv2.imwrite(temp_path, scaled)
        
        text = pytesseract.image_to_string(temp_path, config='--oem 3 --psm 8')
        
        os.remove(temp_path)
        
        text = re.sub(r'[^0-9]', '', text.strip())
        match = re.search(r'(\d{6})', text)
        
        if match:
            return match.group(1)
        return None
    except Exception as e:
        logger.error(f"❌ Fallback OCR error: {e}")
        return None

# ==================== FUNGSI DETEKSI JENIS CAPTCHA ====================

def detect_captcha_type(message):
    """
    Mendeteksi jenis captcha dari pesan Bot A
    Return: dict dengan info jenis captcha
    """
    text = message.text or message.caption or ''
    result = {
        'is_captcha': False,
        'type': None,
        'code': None,
        'data': {}
    }
    
    # LOG LENGKAP UNTUK DEBUG
    logger.info(f"🔍 Detecting captcha type - Photo: {bool(message.photo)}, Text length: {len(text)}")
    
    # ===== LAPIS 1: CEK ANGKA 6 DIGIT DI TEKS =====
    six_digit_numbers = re.findall(r'(\d{6})', text)
    if six_digit_numbers:
        logger.info(f"🔢 Found 6-digit numbers: {six_digit_numbers}")
        
        # Prioritaskan yang pertama
        result['code'] = six_digit_numbers[0]
        
        # Cek apakah ada kata kunci captcha
        if 'captcha' in text.lower() or 'verify' in text.lower() or 'code' in text.lower():
            result['is_captcha'] = True
            result['type'] = 'text_6digit'
            result['data']['source'] = 'text'
            logger.info(f"✅ CAPTCHA from text: {result['code']}")
            return result
    
    # ===== LAPIS 2: CEK FOTO (mungkin captcha gambar) =====
    if message.photo:
        result['is_captcha'] = True
        result['type'] = 'image'
        result['data']['has_text'] = bool(text)
        logger.info(f"📸 PHOTO DETECTED - potential image captcha")
        return result
    
    # ===== LAPIS 3: CEK TOMBOL INLINE =====
    if message.reply_markup and message.reply_markup.inline_keyboard:
        buttons = []
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                buttons.append({
                    'text': btn.text,
                    'data': btn.callback_data
                })
        
        # Jika ada banyak tombol, kemungkinan captcha
        if len(buttons) >= 3:
            result['is_captcha'] = True
            result['type'] = 'inline_buttons'
            result['data']['buttons'] = buttons
            result['data']['question'] = text
            logger.info(f"🔘 INLINE BUTTONS DETECTED - {len(buttons)} buttons")
            return result
    
    # ===== LAPIS 4: CEK PERTANYAAN =====
    if '?' in text and any(opt in text for opt in ['A.', 'B.', 'C.', '1)', '2)', '3)']):
        result['is_captcha'] = True
        result['type'] = 'question'
        result['data']['question'] = text
        # Parse pilihan jawaban
        lines = text.split('\n')
        options = [line.strip() for line in lines if line and ('.' in line or ')' in line)]
        result['data']['options'] = options
        logger.info(f"❓ QUESTION CAPTCHA DETECTED")
        return result
    
    return result

# ==================== HANDLER KHUSUS UNTUK MASING-MASING JENIS CAPTCHA ====================

async def handle_text_captcha(client, captcha_info):
    """Handle captcha teks 6 digit"""
    code = captcha_info['code']
    logger.info(f"📝 Handling text captcha with code: {code}")
    
    # Kirim verifikasi
    await client.send_message(BOT_A_CHAT_ID, f"/verify {code}")
    logger.info(f"✅ Auto-reply sent: /verify {code}")
    return True

async def handle_image_captcha(client, message, captcha_info):
    """Handle captcha gambar dengan OCR"""
    logger.info("🖼️ Handling image captcha with OCR")
    
    # Coba OCR
    code = await solve_captcha_simple(message)
    
    # Kalau gagal, coba fallback
    if not code and message.photo:
        # Download untuk fallback
        photo_path = await message.download()
        img = Image.open(photo_path)
        code = await solve_captcha_fallback(img)
        os.remove(photo_path)
    
    if code:
        await client.send_message(BOT_A_CHAT_ID, f"/verify {code}")
        logger.info(f"✅ OCR success: /verify {code}")
        return True
    else:
        logger.error("❌ OCR failed for image captcha")
        return False

async def handle_inline_captcha(client, message, captcha_info):
    """Handle captcha dengan tombol inline"""
    logger.info("🔘 Handling inline button captcha")
    
    buttons = captcha_info['data']['buttons']
    question = captcha_info['data']['question']
    
    # Strategi 1: Cari angka 6 digit di pertanyaan
    six_digit = re.findall(r'(\d{6})', question)
    if six_digit:
        target = six_digit[0]
        for btn in buttons:
            if target in btn['text']:
                await message.click(btn['text'])
                logger.info(f"✅ Clicked button with {target}")
                return True
    
    # Strategi 2: Coba tombol pertama (fallback)
    if buttons:
        await message.click(buttons[0]['text'])
        logger.info(f"⚠️ Clicked first button as fallback")
        return True
    
    return False

async def handle_question_captcha(client, message, captcha_info):
    """Handle captcha pertanyaan"""
    logger.info("❓ Handling question captcha")
    
    question = captcha_info['data']['question'].lower()
    options = captcha_info['data']['options']
    
    # Deteksi pertanyaan sederhana
    if 'color' in question or 'warna' in question:
        colors = ['red', 'blue', 'green', 'yellow', 'merah', 'biru', 'hijau']
        for opt in options:
            if any(color in opt.lower() for color in colors):
                answer = opt.split('.')[0].strip() if '.' in opt else opt.split(')')[0].strip()
                await client.send_message(BOT_A_CHAT_ID, answer)
                logger.info(f"✅ Answered: {answer}")
                return True
    
    # Fallback: jawab pilihan pertama
    if options:
        first = options[0]
        answer = first.split('.')[0].strip() if '.' in first else first.split(')')[0].strip()
        await client.send_message(BOT_A_CHAT_ID, answer)
        logger.info(f"⚠️ First choice as fallback: {answer}")
        return True
    
    return False

# ==================== KIRIM NOTIFIKASI KE ADMIN ====================

def notify_admin(message):
    """Kirim notifikasi ke admin via Bot B"""
    if os.environ.get('ADMIN_CHAT_ID'):
        try:
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': int(os.environ.get('ADMIN_CHAT_ID')),
                'text': f"🤖 Relay Bot:\n{message}"
            }
            requests.post(url, json=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

# ==================== HANDLER UTAMA PESAN DARI BOT A ====================

@app.on_message(filters.chat(BOT_A_CHAT_ID))
async def handle_bot_reply(client, message: Message):
    """
    Handler utama untuk semua pesan dari Bot A
    """
    text = message.text or message.caption or ''
    
    # LOG LENGKAP
    logger.info(f"🔥 Handler triggered")
    logger.info(f"📸 Has photo: {bool(message.photo)}")
    logger.info(f"🔘 Has reply markup: {bool(message.reply_markup)}")
    logger.info(f"📝 Text preview: {text[:200]}")
    
    # ===== DETEKSI JENIS PESAN =====
    captcha_info = detect_captcha_type(message)
    
    # ===== KALAU INI CAPTCHA, PROSES =====
    if captcha_info['is_captcha']:
        logger.warning(f"🚫 CAPTCHA DETECTED! Type: {captcha_info['type']}")
        bot_status['in_captcha'] = True
        
        notify_admin(f"🚫 Captcha detected: {captcha_info['type']}")
        
        # Proses berdasarkan jenis
        success = False
        
        if captcha_info['type'] == 'text_6digit':
            success = await handle_text_captcha(client, captcha_info)
            
        elif captcha_info['type'] == 'image':
            success = await handle_image_captcha(client, message, captcha_info)
            
        elif captcha_info['type'] == 'inline_buttons':
            success = await handle_inline_captcha(client, message, captcha_info)
            
        elif captcha_info['type'] == 'question':
            success = await handle_question_captcha(client, message, captcha_info)
        
        if success:
            logger.info("✅ Captcha handling successful")
            notify_admin("✅ Captcha solved!")
            
            # Tunggu sebentar biar Bot A proses
            await asyncio.sleep(3)
            
            bot_status['in_captcha'] = False
            
            # Proses ulang request yang pending
            await retry_pending_requests()
        else:
            logger.error("❌ Failed to handle captcha")
            notify_admin("❌ Captcha handling failed, waiting 2 minutes...")
            await asyncio.sleep(120)
            bot_status['in_captcha'] = False
        
        return
    
    # ===== KALAU BUKAN CAPTCHA, FORWARD KE USER =====
    logger.info("📨 Not a captcha, forwarding to user...")
    
    try:
        # Ambil request dari queue
        request_id = r.lpop('pending_requests')
        if request_id:
            request_id = request_id.decode('utf-8')
            request_data_json = r.get(request_id)
            
            # CEK APAKAH DATA MASIH ADA
            if request_data_json is None:
                logger.warning(f"⚠️ Request {request_id} expired, skipping")
                return
            
            request_data = json.loads(request_data_json)
            
            # Kirim ke user via Bot B
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': request_data['chat_id'],
                'text': text,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Forwarded to user {request_data['chat_id']}")
            else:
                logger.error(f"❌ Failed to forward: {response.text}")
                # Kembalikan ke queue
                r.rpush('pending_requests', request_id)
        else:
            logger.debug("No pending requests")
            
    except Exception as e:
        logger.error(f"❌ Forward error: {e}")

# ==================== FUNGSI RETRY REQUEST PENDING ====================

async def retry_pending_requests():
    """
    Kirim ulang semua request yang pending setelah captcha selesai
    """
    logger.info("🔄 Processing pending requests...")
    retry_count = 0
    
    while True:
        request_id = r.lpop('pending_requests')
        if not request_id:
            break
            
        request_id = request_id.decode('utf-8')
        request_data_json = r.get(request_id)
        
        # CEK APAKAH DATA MASIH ADA
        if request_data_json is None:
            logger.warning(f"⚠️ Request {request_id} expired, skipping")
            continue
        
        request_data = json.loads(request_data_json)
        
        # Kirim ulang ke Bot A
        cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
        await app.send_message(BOT_A_CHAT_ID, cmd)
        logger.info(f"🔄 Retry {retry_count+1}: {cmd}")
        
        # Simpan kembali untuk nanti diambil responsenya
        r.setex(request_id, 300, json.dumps(request_data))
        
        retry_count += 1
        await asyncio.sleep(2)
    
    if retry_count > 0:
        logger.info(f"✅ Retried {retry_count} pending requests")

# ==================== HANDLER UNTUK /start (TEST) ====================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    """Handler untuk test koneksi"""
    await message.reply("✅ Relay bot aktif!")
    logger.info("✅ Start command received")

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    """
    Monitor queue Redis dan kirim request ke Bot A
    Berjalan terus menerus
    """
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            # Jangan kirim request baru kalau sedang captcha
            if not bot_status['in_captcha']:
                request_id = r.lpop('pending_requests')
                
                if request_id:
                    request_id = request_id.decode('utf-8')
                    request_data_json = r.get(request_id)
                    
                    # CEK APAKAH DATA MASIH ADA
                    if request_data_json is None:
                        logger.warning(f"⚠️ Request {request_id} expired, skipping")
                        continue
                    
                    request_data = json.loads(request_data_json)
                    
                    # Kirim ke Bot A
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    await app.send_message(BOT_A_CHAT_ID, cmd)
                    logger.info(f"📤 Request sent: {cmd}")
                    
                    # Simpan kembali untuk nanti diambil responsenya
                    r.setex(request_id, 300, json.dumps(request_data))
            
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        # Jeda 3 detik antar loop
        await asyncio.sleep(3)

# ==================== MAIN FUNCTION ====================

async def main():
    """
    Fungsi utama untuk menjalankan bot
    """
    logger.info("🚀 Starting userbot...")
    
    try:
        # Start Pyrogram client
        await app.start()
        logger.info("✅ Userbot started!")
        
        # Test connection ke Bot A
        try:
            await app.send_message(BOT_A_CHAT_ID, "/start")
            logger.info("✅ Connected to Bot A")
        except Exception as e:
            logger.warning(f"⚠️ Could not send /start to Bot A: {e}")
        
        # Kirim notifikasi admin bahwa bot sudah start
        notify_admin("✅ Relay bot started!")
        
        # Jalankan queue processor
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        notify_admin(f"❌ Relay bot failed: {e}")
        raise

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    asyncio.run(main())
