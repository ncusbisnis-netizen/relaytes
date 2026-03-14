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

# ==================== LOGGING ====================

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

STOK_ADMIN_URL = os.environ.get(
    'STOK_ADMIN_URL',
    'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E'
)

# ==================== COUNTRY ====================

country_mapping = {
    'ID': '🇮🇩 Indonesia',
    'MY': '🇲🇾 Malaysia',
    'SG': '🇸🇬 Singapore',
    'PH': '🇵🇭 Philippines',
    'TH': '🇹🇭 Thailand',
}

# ==================== VALIDASI ====================

if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, REDIS_URL]):
    logger.error("❌ Missing ENV")
    exit(1)

# ==================== REDIS ====================

try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis error {e}")
    exit(1)

# ==================== TELEGRAM ====================

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ==================== GLOBAL ====================

bot_status = {'in_captcha': False}

sent_requests = {}
waiting_for_result = {}

downloaded_photos = []
active_requests = {}

captcha_timer_task = None

REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== OCR VHEER ====================

def parse_vheer_response(text):

    try:

        lines = text.split("\n")

        for line in lines:

            if line.startswith("1:"):

                data = json.loads(line[2:])

                captcha = data["paragraphs"][0]["text"]

                numbers = re.findall(r'\d{6}', captcha)

                if numbers:
                    return numbers[0]

        return None

    except Exception as e:
        logger.error(f"OCR parse error {e}")
        return None


def solve_captcha_vheer(image_path):

    try:

        logger.info("📤 Upload ke Vheer")

        files = {
            "file": open(image_path, "rb")
        }

        res = requests.post(
            "https://vheer.com/api/ocr",
            files=files,
            timeout=30
        )

        if res.status_code != 200:
            logger.error("❌ OCR HTTP error")
            return None

        return parse_vheer_response(res.text)

    except Exception as e:
        logger.error(f"❌ OCR error {e}")
        return None


async def read_captcha(message):

    try:

        path = await message.download_media()

        downloaded_photos.append(path)

        logger.info(f"📸 Download captcha {path}")

        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            solve_captcha_vheer,
            path
        )

        return result

    except Exception as e:
        logger.error(f"❌ captcha read error {e}")
        return None


# ==================== CLEANUP ====================

def cleanup_downloaded_photos():

    global downloaded_photos

    for p in downloaded_photos[:]:

        try:

            if os.path.exists(p):

                os.remove(p)

                logger.info(f"🗑️ delete {p}")

            downloaded_photos.remove(p)

        except:
            pass


# ==================== BOT API ====================

async def send_status(chat_id, text, reply_to=None, markup=None):

    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_to:
        data["reply_to_message_id"] = reply_to

    if markup:
        data["reply_markup"] = json.dumps(markup)

    try:

        r = requests.post(url, json=data)

        if r.status_code == 200:

            return r.json()["result"]["message_id"]

    except:
        pass

    return None


async def edit_status(chat_id, msg_id, text, markup=None):

    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"

    data = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text
    }

    if markup:
        data["reply_markup"] = json.dumps(markup)

    try:

        requests.post(url, json=data)

    except:
        pass


# ==================== CAPTCHA HANDLER ====================

@events.register(events.NewMessage)

async def message_handler(event):

    global captcha_timer_task
    global bot_status

    msg = event.message

    if msg.chat_id != 7240340418 and msg.sender_id != 7240340418:
        return

    text = msg.text or msg.message or ''

    logger.info(f"📩 Dari Bot A: {text[:80]}")

    # ================= CAPTCHA =================

    if (msg.photo or "captcha" in text.lower()):

        logger.warning("🚫 CAPTCHA DETECTED")

        bot_status["in_captcha"] = True

        kode = None

        digits = re.findall(r'\d', text)

        if len(digits) >= 6:
            kode = "".join(digits[:6])

        if not kode and msg.photo:

            logger.info("📸 OCR VHEER START")

            kode = await read_captcha(msg)

        if kode and len(kode) == 6:

            await client.send_message(
                BOT_A_USERNAME,
                f"/verify {kode}"
            )

            logger.info(f"✅ CAPTCHA {kode}")

        else:

            logger.error("❌ OCR gagal")

        cleanup_downloaded_photos()

        bot_status["in_captcha"] = False


# ==================== QUEUE ====================

async def process_queue():

    logger.info("🔄 Queue start")

    while True:

        try:

            if not bot_status["in_captcha"]:

                req = r.lindex("pending_requests", 0)

                if req:

                    req_id = req.decode()

                    data = r.get(req_id)

                    if not data:
                        r.lpop("pending_requests")
                        continue

                    req_data = json.loads(data)

                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"

                    await client.send_message(
                        BOT_A_USERNAME,
                        cmd
                    )

                    logger.info(f"📤 send {cmd}")

        except Exception as e:

            logger.error(f"queue error {e}")

        await asyncio.sleep(2)


# ==================== MAIN ====================

async def main():

    logger.info("🚀 START USERBOT")

    await client.start()

    me = await client.get_me()

    logger.info(f"LOGIN {me.first_name}")

    client.add_event_handler(message_handler)

    await process_queue()


if __name__ == "__main__":

    asyncio.run(main())
