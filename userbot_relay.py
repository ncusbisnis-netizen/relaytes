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
from datetime import datetime

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
BOT_BIND_USERNAME = 'stasiunmlbb_bot'
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# ==================== AUTO REDEEM CONFIG ====================
AUTO_REDEEM_ENABLED = os.environ.get('AUTO_REDEEM_ENABLED', 'true').lower() == 'true'
AUTO_REDEEM_CHANNEL = os.environ.get('AUTO_REDEEM_CHANNEL', 'bengkelmlbb_info')
REDEEM_DELAY = int(os.environ.get('REDEEM_DELAY', '0'))

# ==================== ANTRIAN CONFIG ====================
MAX_CONCURRENT = int(os.environ.get('MAX_CONCURRENT', '1'))  # Maksimal proses bersamaan
QUEUE_TIMEOUT = int(os.environ.get('QUEUE_TIMEOUT', '60'))   # Timeout antrian per user

# ==================== COUNTRY MAPPING ====================
country_mapping = {
  'AF': '🇦🇫 Afghanistan',
  'AX': '🇦🇽 Åland Islands',
  'AL': '🇦🇱 Albania',
  'DZ': '🇩🇿 Algeria',
  'AS': '🇦🇸 American Samoa',
  'AD': '🇦🇩 Andorra',
  'AO': '🇦🇴 Angola',
  'AI': '🇦🇮 Anguilla',
  'AQ': '🇦🇶 Antarctica',
  'AG': '🇦🇬 Antigua and Barbuda',
  'AR': '🇦🇷 Argentina',
  'AM': '🇦🇲 Armenia',
  'AW': '🇦🇼 Aruba',
  'AU': '🇦🇺 Australia',
  'AT': '🇦🇹 Austria',
  'AZ': '🇦🇿 Azerbaijan',
  'BS': '🇧🇸 Bahamas',
  'BH': '🇧🇭 Bahrain',
  'BD': '🇧🇩 Bangladesh',
  'BB': '🇧🇧 Barbados',
  'BY': '🇧🇾 Belarus',
  'BE': '🇧🇪 Belgium',
  'BZ': '🇧🇿 Belize',
  'BJ': '🇧🇯 Benin',
  'BM': '🇧🇲 Bermuda',
  'BT': '🇧🇹 Bhutan',
  'BO': '🇧🇴 Bolivia, Plurinational State of bolivia',
  'BA': '🇧🇦 Bosnia and Herzegovina',
  'BW': '🇧🇼 Botswana',
  'BV': '🇧🇻 Bouvet Island',
  'BR': '🇧🇷 Brazil',
  'IO': '🇮🇴 British Indian Ocean Territory',
  'BN': '🇧🇳 Brunei Darussalam',
  'BG': '🇧🇬 Bulgaria',
  'BF': '🇧🇫 Burkina Faso',
  'BI': '🇧🇮 Burundi',
  'KH': '🇰🇭 Cambodia',
  'CM': '🇨🇲 Cameroon',
  'CA': '🇨🇦 Canada',
  'CV': '🇨🇻 Cape Verde',
  'KY': '🇰🇾 Cayman Islands',
  'CF': '🇨🇫 Central African Republic',
  'TD': '🇹🇩 Chad',
  'CL': '🇨🇱 Chile',
  'CN': '🇨🇳 China',
  'CX': '🇨🇽 Christmas Island',
  'CC': '🇨🇨 Cocos (Keeling) Islands',
  'CO': '🇨🇴 Colombia',
  'KM': '🇰🇲 Comoros',
  'CG': '🇨🇬 Congo',
  'CD': '🇨🇩 Congo, The Democratic Republic of the Congo',
  'CK': '🇨🇰 Cook Islands',
  'CR': '🇨🇷 Costa Rica',
  'CI': "🇨🇮 Cote d'Ivoire",
  'HR': '🇭🇷 Croatia',
  'CU': '🇨🇺 Cuba',
  'CY': '🇨🇾 Cyprus',
  'CZ': '🇨🇿 Czech Republic',
  'DK': '🇩🇰 Denmark',
  'DJ': '🇩🇯 Djibouti',
  'DM': '🇩🇲 Dominica',
  'DO': '🇩🇴 Dominican Republic',
  'EC': '🇪🇨 Ecuador',
  'EG': '🇪🇬 Egypt',
  'SV': '🇸🇻 El Salvador',
  'GQ': '🇬🇶 Equatorial Guinea',
  'ER': '🇪🇷 Eritrea',
  'EE': '🇪🇪 Estonia',
  'ET': '🇪🇹 Ethiopia',
  'FK': '🇫🇰 Falkland Islands (Malvinas)',
  'FO': '🇫🇴 Faroe Islands',
  'FJ': '🇫🇯 Fiji',
  'FI': '🇫🇮 Finland',
  'FR': '🇫🇷 France',
  'GF': '🇬🇫 French Guiana',
  'PF': '🇵🇫 French Polynesia',
  'TF': '🇹🇫 French Southern Territories',
  'GA': '🇬🇦 Gabon',
  'GM': '🇬🇲 Gambia',
  'GE': '🇬🇪 Georgia',
  'DE': '🇩🇪 Germany',
  'GH': '🇬🇭 Ghana',
  'GI': '🇬🇮 Gibraltar',
  'GR': '🇬🇷 Greece',
  'GL': '🇬🇱 Greenland',
  'GD': '🇬🇩 Grenada',
  'GP': '🇬🇵 Guadeloupe',
  'GU': '🇬🇺 Guam',
  'GT': '🇬🇹 Guatemala',
  'GG': '🇬🇬 Guernsey',
  'GN': '🇬🇳 Guinea',
  'GW': '🇬🇼 Guinea-Bissau',
  'GY': '🇬🇾 Guyana',
  'HT': '🇭🇹 Haiti',
  'HM': '🇭🇲 Heard Island and Mcdonald Islands',
  'VA': '🇻🇦 Holy See (Vatican City State)',
  'HN': '🇭🇳 Honduras',
  'HK': '🇭🇰 Hong Kong',
  'HU': '🇭🇺 Hungary',
  'IS': '🇮🇸 Iceland',
  'IN': '🇮🇳 India',
  'ID': '🇮🇩 Indonesia',
  'IR': '🇮🇷 Iran, Islamic Republic of Persian Gulf',
  'IQ': '🇮🇶 Iraq',
  'IE': '🇮🇪 Ireland',
  'IM': '🇮🇲 Isle of Man',
  'IL': '🇮🇱 Israel',
  'IT': '🇮🇹 Italy',
  'JM': '🇯🇲 Jamaica',
  'JP': '🇯🇵 Japan',
  'JE': '🇯🇪 Jersey',
  'JO': '🇯🇴 Jordan',
  'KZ': '🇰🇿 Kazakhstan',
  'KE': '🇰🇪 Kenya',
  'KI': '🇰🇮 Kiribati',
  'KP': "🇰🇵 Korea, Democratic People's Republic of Korea",
  'KR': '🇰🇷 Korea, Republic of South Korea',
  'XK': '🇽🇰 Kosovo',
  'KW': '🇰🇼 Kuwait',
  'KG': '🇰🇬 Kyrgyzstan',
  'LA': '🇱🇦 Laos',
  'LV': '🇱🇻 Latvia',
  'LB': '🇱🇧 Lebanon',
  'LS': '🇱🇸 Lesotho',
  'LR': '🇱🇷 Liberia',
  'LY': '🇱🇾 Libyan Arab Jamahiriya',
  'LI': '🇱🇮 Liechtenstein',
  'LT': '🇱🇹 Lithuania',
  'LU': '🇱🇺 Luxembourg',
  'MO': '🇲🇴 Macao',
  'MK': '🇲🇰 Macedonia',
  'MG': '🇲🇬 Madagascar',
  'MW': '🇲🇼 Malawi',
  'MY': '🇲🇾 Malaysia',
  'MV': '🇲🇻 Maldives',
  'ML': '🇲🇱 Mali',
  'MT': '🇲🇹 Malta',
  'MH': '🇲🇭 Marshall Islands',
  'MQ': '🇲🇶 Martinique',
  'MR': '🇲🇷 Mauritania',
  'MU': '🇲🇺 Mauritius',
  'YT': '🇾🇹 Mayotte',
  'MX': '🇲🇽 Mexico',
  'FM': '🇫🇲 Micronesia, Federated States of Micronesia',
  'MD': '🇲🇩 Moldova',
  'MC': '🇲🇨 Monaco',
  'MN': '🇲🇳 Mongolia',
  'ME': '🇲🇪 Montenegro',
  'MS': '🇲🇸 Montserrat',
  'MA': '🇲🇦 Morocco',
  'MZ': '🇲🇿 Mozambique',
  'MM': '🇲🇲 Myanmar',
  'NA': '🇳🇦 Namibia',
  'NR': '🇳🇷 Nauru',
  'NP': '🇳🇵 Nepal',
  'NL': '🇳🇱 Netherlands',
  'AN': 'Netherlands Antilles',
  'NC': '🇳🇨 New Caledonia',
  'NZ': '🇳🇿 New Zealand',
  'NI': '🇳🇮 Nicaragua',
  'NE': '🇳🇪 Niger',
  'NG': '🇳🇬 Nigeria',
  'NU': '🇳🇺 Niue',
  'NF': '🇳🇫 Norfolk Island',
  'MP': '🇲🇵 Northern Mariana Islands',
  'NO': '🇳🇴 Norway',
  'OM': '🇴🇲 Oman',
  'PK': '🇵🇰 Pakistan',
  'PW': '🇵🇼 Palau',
  'PS': '🇵🇸 Palestinian Territory, Occupied',
  'PA': '🇵🇦 Panama',
  'PG': '🇵🇬 Papua New Guinea',
  'PY': '🇵🇾 Paraguay',
  'PE': '🇵🇪 Peru',
  'PH': '🇵🇭 Philippines',
  'PN': '🇵🇳 Pitcairn',
  'PL': '🇵🇱 Poland',
  'PT': '🇵🇹 Portugal',
  'PR': '🇵🇷 Puerto Rico',
  'QA': '🇶🇦 Qatar',
  'RO': '🇷🇴 Romania',
  'RU': '🇷🇺 Russia',
  'RW': '🇷🇼 Rwanda',
  'RE': '🇷🇪 Reunion',
  'BL': '🇧🇱 Saint Barthelemy',
  'SH': '🇸🇭 Saint Helena, Ascension and Tristan Da Cunha',
  'KN': '🇰🇳 Saint Kitts and Nevis',
  'LC': '🇱🇨 Saint Lucia',
  'MF': '🇲🇫 Saint Martin',
  'PM': '🇵🇲 Saint Pierre and Miquelon',
  'VC': '🇻🇨 Saint Vincent and the Grenadines',
  'WS': '🇼🇸 Samoa',
  'SM': '🇸🇲 San Marino',
  'ST': '🇸🇹 Sao Tome and Principe',
  'SA': '🇸🇦 Saudi Arabia',
  'SN': '🇸🇳 Senegal',
  'RS': '🇷🇸 Serbia',
  'SC': '🇸🇨 Seychelles',
  'SL': '🇸🇱 Sierra Leone',
  'SG': '🇸🇬 Singapore',
  'SK': '🇸🇰 Slovakia',
  'SI': '🇸🇮 Slovenia',
  'SB': '🇸🇧 Solomon Islands',
  'SO': '🇸🇴 Somalia',
  'ZA': '🇿🇦 South Africa',
  'SS': '🇸🇸 South Sudan',
  'GS': '🇬🇸 South Georgia and the South Sandwich Islands',
  'ES': '🇪🇸 Spain',
  'LK': '🇱🇰 Sri Lanka',
  'SD': '🇸🇩 Sudan',
  'SR': '🇸🇷 Suriname',
  'SJ': '🇸🇯 Svalbard and Jan Mayen',
  'SZ': '🇸🇿 Eswatini',
  'SE': '🇸🇪 Sweden',
  'CH': '🇨🇭 Switzerland',
  'SY': '🇸🇾 Syrian Arab Republic',
  'TW': '🇹🇼 Taiwan',
  'TJ': '🇹🇯 Tajikistan',
  'TZ': '🇹🇿 Tanzania, United Republic of Tanzania',
  'TH': '🇹🇭 Thailand',
  'TL': '🇹🇱 Timor-Leste',
  'TG': '🇹🇬 Togo',
  'TK': '🇹🇰 Tokelau',
  'TO': '🇹🇴 Tonga',
  'TT': '🇹🇹 Trinidad and Tobago',
  'TN': '🇹🇳 Tunisia',
  'TR': '🇹🇷 Turkey',
  'TM': '🇹🇲 Turkmenistan',
  'TC': '🇹🇨 Turks and Caicos Islands',
  'TV': '🇹🇻 Tuvalu',
  'UG': '🇺🇬 Uganda',
  'UA': '🇺🇦 Ukraine',
  'AE': '🇦🇪 United Arab Emirates',
  'GB': '🇬🇧 United Kingdom',
  'US': '🇺🇸 United States',
  'UY': '🇺🇾 Uruguay',
  'UZ': '🇺🇿 Uzbekistan',
  'VU': '🇻🇺 Vanuatu',
  'VE': '🇻🇪 Venezuela, Bolivarian Republic of Venezuela',
  'VN': '🇻🇳 Vietnam',
  'VG': '🇻🇬 Virgin Islands, British',
  'VI': '🇻🇮 Virgin Islands, U.S.',
  'WF': '🇼🇫 Wallis and Futuna',
  'YE': '🇾🇪 Yemen',
  'ZM': '🇿🇲 Zambia',
  'ZW': '🇿🇼 Zimbabwe',
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
active_requests = {}      # { req_id: {...} }
active_count = 0          # Jumlah proses aktif
captcha_timer_task = None

# Data untuk bind
pending_bind = {}          # { chat_id: {'uid': ..., 'server': ..., 'start_time': ...} }
pending_bind_wait = {}     # { chat_id: asyncio.Event() }
bind_data = {}             # { chat_id: {'creation': ..., 'last_login': ...} }
BIND_WAIT_TIMEOUT = 15     # detik menunggu respons bind

REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# Queue untuk menampung user yang menunggu
waiting_queue = []         # List of (user_id, req_id, req_data)
queue_locks = {}           # { user_id: asyncio.Lock } untuk mencegah duplicate

# ==================== AUTO REDEEM MANAGER ====================
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
    """OCR menggunakan OCR Space API"""
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

def format_final_output(original_text, nickname, region, uid, sid, android, ios, creation=None, last_login=None):
    """Format output final dengan menambahkan creation dan last_login jika ada"""
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
    
    # Tambahkan informasi creation dan last_login jika tersedia
    extra_info = ""
    if creation:
        extra_info += f"\nYear Creation: {creation}"
    if last_login:
        extra_info += f"\nLast Login: {last_login}"
    
    final = f"""INFORMATION ACCOUNT:
ID Server: {uid} ({sid})
Nickname: {nickname}
Region: {region}{extra_info}

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

# ==================== TIMEOUT CHECKER ====================
async def timeout_checker():
    while True:
        if bot_status['in_captcha']:
            await asyncio.sleep(1)
            continue

        now = time.time()
        # Timeout untuk request info
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
        
        # Timeout untuk bind request
        bind_timeout = []
        for chat_id, bind_info in list(pending_bind.items()):
            if now - bind_info['start_time'] > BIND_WAIT_TIMEOUT + 5:
                logger.warning(f"⏰ Bind timeout untuk user {chat_id}")
                bind_timeout.append(chat_id)
        for chat_id in bind_timeout:
            pending_bind.pop(chat_id, None)
            if chat_id in pending_bind_wait:
                pending_bind_wait[chat_id].set()
                pending_bind_wait.pop(chat_id, None)
        
        await asyncio.sleep(1)

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
    
    await send_status_to_user(7240340418, f"🎯 *VOUCHER DETECTED!*\nCodes: {len(new_codes)}\n{', '.join(new_codes)}")
    
    for i, code in enumerate(new_codes, 1):
        if i > 1:
            logger.info(f"⏳ Waiting {REDEEM_DELAY}s before next code...")
            await asyncio.sleep(REDEEM_DELAY)
        
        success = await send_redeem_command(code)
        
        if success:
            auto_redeem.add_redeemed(code)
            await send_status_to_user(7240340418, f"✅ Sent: `{code}`")
        else:
            auto_redeem.add_failed(code)
            await send_status_to_user(7240340418, f"❌ Failed: `{code}`")
    
    auto_redeem.save()

# ==================== FUNGSI PROSES REQUEST ====================
async def process_request(user_id, req_id, req_data):
    """Proses request untuk satu user"""
    global active_count
    
    try:
        reply_to_message_id = req_data.get('reply_to_message_id')
        
        # Kirim status awal ke user
        msg_id = await send_status_to_user(user_id, "Proses request...", reply_to_message_id)
        if not msg_id:
            logger.error(f"❌ Gagal mengirim status ke user {user_id}")
            return False
        
        # Simpan request info aktif
        active_requests[req_id] = {
            'chat_id': user_id,
            'message_id': msg_id,
            'start_time': time.time(),
            'command': req_data['command'],
            'args': req_data['args']
        }
        
        # Kirim perintah /info ke Bot A
        cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
        await client.send_message(BOT_A_USERNAME, cmd)
        logger.info(f"📤 Mengirim ke Bot A: {cmd}")
        
        # Kirim perintah /bind ke Bot Bind
        uid = req_data['args'][0]
        server = req_data['args'][1]
        bind_cmd = f"/bind {uid} {server}"
        await client.send_message(BOT_BIND_USERNAME, bind_cmd)
        logger.info(f"📤 Mengirim ke {BOT_BIND_USERNAME}: {bind_cmd}")
        
        # Catat pending bind
        pending_bind[user_id] = {
            'uid': uid,
            'server': server,
            'start_time': time.time(),
            'status_msg_id': msg_id
        }
        
        sent_requests[req_id] = time.time()
        waiting_for_result[user_id] = True
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing request: {e}")
        return False

async def finish_request(req_id, user_id, success=True):
    """Selesaikan request"""
    global active_count
    
    if req_id in active_requests:
        active_requests.pop(req_id, None)
    
    waiting_for_result.pop(user_id, None)
    
    # Hapus dari Redis
    try:
        head = r.lindex('pending_requests', 0)
        if head and head.decode('utf-8') == req_id:
            r.lpop('pending_requests')
        r.delete(req_id)
    except Exception as e:
        logger.error(f"❌ Gagal hapus Redis: {e}")
    
    active_count -= 1
    logger.info(f"✅ Request selesai, aktif: {active_count}")

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

    # ========== 1. HASIL INFO ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info dari Bot A")
        
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif, hasil diabaikan")
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

        # Ambil nickname dan region dari GoPay
        gopay = validate_mlbb_gopay_sync(uid, sid)
        if gopay['status']:
            nickname = gopay['username']
            region = gopay['region']
        else:
            nickname = 'Tidak diketahui'
            region = '🌍 Tidak diketahui'

        # TUNGGU BIND RESPONSE
        creation = None
        last_login = None
        
        if user_id in pending_bind:
            if user_id not in pending_bind_wait:
                pending_bind_wait[user_id] = asyncio.Event()
            
            try:
                await asyncio.wait_for(pending_bind_wait[user_id].wait(), timeout=BIND_WAIT_TIMEOUT)
                logger.info(f"✅ Bind data diterima tepat waktu untuk user {user_id}")
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Bind timeout untuk user {user_id}")
            
            bind_info = bind_data.get(user_id)
            if bind_info:
                creation = bind_info.get('creation')
                last_login = bind_info.get('last_login')
                bind_data.pop(user_id, None)
            
            pending_bind_wait.pop(user_id, None)
            pending_bind.pop(user_id, None)

        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios, creation, last_login)
        await edit_status_message(user_id, message_id, output, markup)

        # Selesaikan request
        await finish_request(req_id, user_id)
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
        else:
            logger.warning("⚠️ Tidak ada request aktif untuk auto-retry")
        return

    # ========== 3. ERROR HANDLING ==========
    if any(kw in text.lower() for kw in ['kesalahan', 'error', 'gagal']):
        logger.info(f"❌ Mendeteksi pesan error dari Bot A: {text[:100]}")
        
        if active_requests:
            req_id, req_info = next(iter(active_requests.items()))
            user_id = req_info['chat_id']
            message_id = req_info['message_id']
            
            await edit_status_message(user_id, message_id, "❌ Gagal memproses request. Coba lagi.")
            await finish_request(req_id, user_id)
        
        cleanup_downloaded_photos()
        return

    # ========== 4. CAPTCHA ==========
    if (message.photo or 
        'captcha' in text.lower() or 
        re.search(r'\d{6}', text) or 
        '🔒 Masukkan kode captcha' in text):
        
        logger.warning("🚫 CAPTCHA terdeteksi!")
        bot_status['in_captcha'] = True

        if active_requests:
            for req_id, req_info in active_requests.items():
                req_info['start_time'] = time.time()
                logger.info(f"⏱️ Reset timeout untuk request {req_id} karena captcha")
        else:
            logger.warning("⚠️ Captcha terdeteksi tapi tidak ada request aktif")

        if captcha_timer_task:
            captcha_timer_task.cancel()

        async def reset_captcha():
            await asyncio.sleep(CAPTCHA_TIMEOUT)
            bot_status['in_captcha'] = False
            logger.info("Captcha timeout, status direset")
        captcha_timer_task = asyncio.create_task(reset_captcha())

        captcha_code = None

        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"🔑 Kode captcha dari teks: {captcha_code}")

        if not captcha_code and message.photo:
            for attempt in range(2):
                try:
                    logger.info(f"📸 Percobaan OCR ke-{attempt+1}")
                    captcha_code = await read_number_from_photo_online(message)
                    if captcha_code:
                        logger.info(f"🔑 Kode captcha dari OCR: {captcha_code}")
                        break
                except Exception as e:
                    logger.error(f"❌ OCR percobaan {attempt+1} error: {e}")
                if attempt == 0:
                    await asyncio.sleep(2)

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
                    "❌ Gagal memproses request. Coba lagi."
                )
                await finish_request(req_id, req_info['chat_id'])

            bot_status['in_captcha'] = False
            if captcha_timer_task:
                captcha_timer_task.cancel()
                captcha_timer_task = None

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

# ==================== HANDLER UNTUK BOT BIND ====================
@events.register(events.MessageEdited)
@events.register(events.NewMessage)
async def bind_response_handler(event):
    """Menangkap respons dari @stasiunmlbb_bot"""
    message = event.message
    sender = await message.get_sender()
    
    if not sender or sender.username != BOT_BIND_USERNAME:
        return
    
    text = message.text or ''
    logger.info(f"📩 Dari {BOT_BIND_USERNAME}: {text[:200]}")
    
    if "Bind Result" not in text:
        logger.info("⏳ Pesan loading bind, diabaikan")
        return
    
    uid_match = re.search(r'🆔.*?(\d+)', text)
    if not uid_match:
        logger.warning("❌ Tidak dapat menemukan UID")
        return
    
    uid = uid_match.group(1)
    logger.info(f"🔍 Ekstrak UID: {uid}")
    
    target_chat = None
    for chat_id, info in pending_bind.items():
        if info.get('uid') == uid:
            target_chat = chat_id
            break
    
    if not target_chat:
        logger.warning(f"⚠️ Tidak ada pending bind untuk UID {uid}")
        return
    
    creation_match = re.search(r'🕰.*?Creation.*?(\d{4})', text)
    creation = creation_match.group(1) if creation_match else None
    
    last_login_match = re.search(r'🕒.*?Last Login.*?:\s*(.+?)(?:\n|$)', text)
    last_login = last_login_match.group(1).strip() if last_login_match else None
    
    if last_login:
        last_login = re.sub(r'[*_`]', '', last_login)
        last_login = re.sub(r'\s*(PHT|WIB|WITA|WIT|UTC|GMT)[^\s]*', '', last_login, flags=re.IGNORECASE)
        last_login = re.sub(r'\s+', ' ', last_login).strip()
    
    bind_data[target_chat] = {
        'creation': creation,
        'last_login': last_login
    }
    
    if target_chat in pending_bind_wait:
        pending_bind_wait[target_chat].set()
    
    pending_bind.pop(target_chat, None)
    logger.info(f"✅ Bind data: creation={creation}, last_login={last_login}")

# ==================== PROSES ANTRIAN DENGAN THROTTLING ====================
async def process_queue():
    """Proses antrian dengan batasan concurrent"""
    global active_count
    
    logger.info(f"🔄 Queue processor started (Max concurrent: {MAX_CONCURRENT})")
    
    while True:
        try:
            # Jika tidak dalam captcha dan masih ada slot kosong
            if not bot_status['in_captcha'] and active_count < MAX_CONCURRENT:
                req_bytes = r.lindex('pending_requests', 0)
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now = time.time()
                    
                    # Cek jika request sudah dikirim baru-baru ini
                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2)
                        continue
                    
                    req_json = r.get(req_id)
                    if not req_json:
                        logger.warning(f"⚠️ Request {req_id} tidak ditemukan")
                        r.lpop('pending_requests')
                        continue
                    
                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                    
                    # Cek apakah user sedang dalam proses
                    if waiting_for_result.get(user_id, False):
                        logger.info(f"⏳ User {user_id} masih menunggu, pindahkan ke belakang")
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(2)
                        continue
                    
                    # Proses request
                    logger.info(f"🚀 Memproses request untuk user {user_id} (Aktif: {active_count+1}/{MAX_CONCURRENT})")
                    active_count += 1
                    
                    success = await process_request(user_id, req_id, req_data)
                    
                    if not success:
                        active_count -= 1
                        r.lpop('pending_requests')
                        r.delete(req_id)
                    
            else:
                if active_count >= MAX_CONCURRENT:
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            logger.error(f"❌ Error di process_queue: {e}")
            await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot...")
    logger.info(f"📊 Max Concurrent: {MAX_CONCURRENT}")
    logger.info(f"📊 Queue Timeout: {QUEUE_TIMEOUT}s")

    # Load data auto redeem
    auto_redeem.load()
    logger.info(f"📊 Auto Redeem: {'✅ ACTIVE' if AUTO_REDEEM_ENABLED else '❌ DISABLED'}")

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

        # Daftarkan event handler
        client.add_event_handler(message_handler)
        client.add_event_handler(auto_redeem_handler)
        client.add_event_handler(bind_response_handler)

        # Jalankan timeout checker
        asyncio.create_task(timeout_checker())

        # Jalankan pemrosesan antrian
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
