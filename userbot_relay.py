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

# ==================== CONFIG ====================

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

BOT_B_TOKEN = os.environ.get("BOT_B_TOKEN", "")
BOT_A_USERNAME = "bengkelmlbb_bot"

REDIS_URL = os.environ.get("REDIS_URL")

# ==================== VALIDASI ====================

if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, REDIS_URL]):
    logger.error("❌ ENV belum lengkap")
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

bot_status = {"in_captcha": False}

sent_requests = {}
waiting_for_result = {}

downloaded_photos = []
active_requests = {}

# ==================== OCR VHEER ====================

def parse_vheer(text):

    try:

        lines = text.split("\n")

        for line in lines:

            if line.startswith("1:"):

                data = json.loads(line[2:])

                captcha = data["paragraphs"][0]["text"]

                angka = re.findall(r"\d{6}", captcha)

                if angka:
                    return angka[0]

        return None

    except Exception as e:

        logger.error(f"OCR parse error {e}")

        return None


def solve_vheer(image_path):

    try:

        logger.info("📤 Upload ke Vheer")

        with open(image_path, "rb") as f:

            files = {
                "file": ("captcha.jpg", f, "image/jpeg")
            }

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*"
            }

            res = requests.post(
                "https://vheer.com/app/api/image-to-text",
                files=files,
                headers=headers,
                timeout=30
            )

        logger.info(f"📡 HTTP {res.status_code}")

        if res.status_code != 200:
            return None

        return parse_vheer(res.text)

    except Exception as e:

        logger.error(f"OCR error {e}")

        return None


async def read_captcha(message):

    try:

        path = await message.download_media()

        downloaded_photos.append(path)

        logger.info(f"📸 Download captcha {path}")

        loop = asyncio.get_event_loop()

        for i in range(3):

            logger.info(f"OCR attempt {i+1}")

            result = await loop.run_in_executor(
                None,
                solve_vheer,
                path
            )

            if result:
                return result

            await asyncio.sleep(2)

        return None

    except Exception as e:

        logger.error(f"captcha error {e}")

        return None


# ==================== CLEANUP ====================

def cleanup_photos():

    global downloaded_photos

    for p in downloaded_photos[:]:

        try:

            if os.path.exists(p):

                os.remove(p)

                logger.info(f"🗑️ delete {p}")

            downloaded_photos.remove(p)

        except:
            pass


# ==================== CAPTCHA HANDLER ====================

@events.register(events.NewMessage)

async def message_handler(event):

    global bot_status

    msg = event.message

    text = msg.text or msg.message or ""

    if msg.chat_id != 7240340418 and msg.sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:80]}")

    # CAPTCHA

    if msg.photo or "captcha" in text.lower() or "🔒" in text:

        logger.warning("🚫 CAPTCHA DETECTED")

        bot_status["in_captcha"] = True

        kode = None

        digits = re.findall(r"\d", text)

        if len(digits) >= 6:
            kode = "".join(digits[:6])

        if not kode and msg.photo:

            logger.info("📸 OCR START")

            kode = await read_captcha(msg)

        if kode and len(kode) == 6:

            logger.info(f"✅ CAPTCHA {kode}")

            await client.send_message(
                BOT_A_USERNAME,
                f"/verify {kode}"
            )

            await asyncio.sleep(5)

        else:

            logger.error("❌ OCR gagal")

        cleanup_photos()

        bot_status["in_captcha"] = False


# ==================== QUEUE ====================

async def process_queue():

    logger.info("🔄 Queue started")

    while True:

        try:

            if bot_status["in_captcha"]:
                await asyncio.sleep(2)
                continue

            req = r.lindex("pending_requests", 0)

            if req:

                req_id = req.decode()

                data = r.get(req_id)

                if not data:
                    r.lpop("pending_requests")
                    continue

                req_data = json.loads(data)

                cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"

                logger.info(f"📤 send {cmd}")

                await client.send_message(
                    BOT_A_USERNAME,
                    cmd
                )

                await asyncio.sleep(3)

        except Exception as e:

            logger.error(f"queue error {e}")

        await asyncio.sleep(2)


# ==================== MAIN ====================

async def main():

    logger.info("🚀 START BOT")

    await client.start()

    me = await client.get_me()

    logger.info(f"LOGIN {me.first_name}")

    client.add_event_handler(message_handler)

    await process_queue()


if __name__ == "__main__":

    asyncio.run(main())
