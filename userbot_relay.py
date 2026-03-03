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
BOT_A_USERNAME = 'bengkelmlbb_bot'
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# Country mapping LENGKAP
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
  'ZW': '🇿🇼 Zimbabwe'
}

# Validasi environment
if not all([API_ID, API_HASH, SESSION_STRING, BOT_B_TOKEN, REDIS_URL]):
    logger.error("❌ Missing required environment variables!")
    exit(1)

if not OCR_SPACE_API_KEY:
    logger.warning("⚠️ OCR_SPACE_API_KEY tidak ditemukan! OCR online tidak akan berfungsi.")

# Redis connection
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

# Telethon Client
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

bot_status = {'in_captcha': False}
sent_requests = {}  # {req_id: {'first_sent': time, 'last_sent': time, 'user_id': id, 'attempts': int}}
waiting_for_result = {}
downloaded_photos = []

MAX_ATTEMPTS = 3
TIMEOUT = 15
TOTAL_TIMEOUT = 30

# ==================== FUNGSI CLEANUP TEXT ====================

def clean_bind_text(text):
    """Bersihkan text bind info"""
    
    # Handle (Private) dan variasinya
    text = re.sub(r'\(Private\)', 'Hide information', text)
    text = re.sub(r'Bind \(Private\)', 'Hide information', text)
    text = re.sub(r'Private', 'Hide information', text)
    
    # Handle Moonton Unverified (khusus Moonton)
    if 'Moonton Unverified' in text:
        parts = text.split('Moonton :', 1)
        if len(parts) > 1:
            text = f"{parts[0]}Moonton : empty."
    
    # Handle (Unverified) untuk yang lain
    text = re.sub(r'\(Unverified\)', 'Failed Verification', text)
    text = re.sub(r'Unverified', 'Failed Verification', text)
    
    # Bersihkan spasi berlebih
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# ==================== FUNGSI VALIDASI GOPAY ====================

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

# ==================== OCR ONLINE ====================

async def read_number_from_photo_online(message):
    try:
        if not OCR_SPACE_API_KEY:
            return None
        
        logger.info("📸 Downloading captcha photo...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        logger.info("📤 Sending to OCR.space API...")
        response = requests.post(
            'https://api.ocr.space/parse/image',
            data={
                'base64Image': f'data:image/jpeg;base64,{image_data}',
                'apikey': OCR_SPACE_API_KEY,
                'language': 'eng',
                'OCREngine': '2'
            },
            timeout=30
        )
        
        logger.info(f"📥 OCR Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if not result.get('IsErroredOnProcessing'):
                text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                logger.info(f"📝 OCR raw text: {text}")
                text = re.sub(r'[^0-9]', '', text)
                match = re.search(r'(\d{6})', text)
                if match:
                    code = match.group(1)
                    logger.info(f"✅ OCR success: {code}")
                    return code
                else:
                    logger.warning("❌ No 6-digit found in OCR result")
            else:
                error = result.get('ErrorMessage', ['Unknown error'])[0]
                logger.error(f"❌ OCR Error: {error}")
        else:
            logger.error(f"❌ OCR API Error: {response.status_code}")
            
        return None
    except Exception as e:
        logger.error(f"❌ OCR error: {e}")
        return None

# ==================== CLEANUP PHOTOS ====================

def cleanup_downloaded_photos():
    global downloaded_photos
    for photo_path in downloaded_photos[:]:
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
                logger.info(f"🧹 Deleted: {photo_path}")
            downloaded_photos.remove(photo_path)
        except Exception as e:
            logger.error(f"❌ Failed to delete {photo_path}: {e}")

# ==================== FORMAT OUTPUT ====================

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    """Format output final"""
    
    keywords = ['Moonton', 'VK', 'Google Play', 'Tiktok', 'Facebook', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    bind_info = []
    
    for kw in keywords:
        found = False
        for line in original_text.split('\n'):
            if kw in line:
                clean_line = line.replace('✧', '•').strip()
                clean_line = re.sub(r'\s+', ' ', clean_line)
                
                # Terapkan cleanup
                clean_line = clean_bind_text(clean_line)
                
                if ':' in clean_line:
                    parts = clean_line.split(':', 1)
                    clean_line = f"{parts[0].strip()}: {parts[1].strip()}"
                bind_info.append(clean_line)
                found = True
                break
        if not found:
            bind_info.append(f"• {kw} : empty.")
    
    final = f"""INFORMATION ACCOUNT
ID: {uid}
Server: {sid}
Nickname: {nickname}
Region: {region}

BIND INFO:
{chr(10).join(bind_info)}

Device Login:
• Android: {android} perangkat
• iOS: {ios} perangkat"""

    reply_markup = {
        'inline_keyboard': [
            [{'text': 'STOK ADMIN', 'url': STOK_ADMIN_URL}]
        ]
    }
    
    return final, reply_markup

# ==================== SEND TO BOT B ====================

async def send_to_bot_b(user_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': user_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        logger.info(f"📤 Mengirim ke user {user_id}...")
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ TERKIRIM KE USER {user_id}")
            
            # Hapus semua request untuk user ini
            try:
                queue_len = r.llen('pending_requests')
                for i in range(queue_len):
                    req_bytes = r.lindex('pending_requests', i)
                    if req_bytes:
                        req_id = req_bytes.decode('utf-8')
                        req_json = r.get(req_id)
                        if req_json:
                            req_data = json.loads(req_json)
                            if req_data['chat_id'] == user_id:
                                r.lrem('pending_requests', 0, req_id)
                                r.delete(req_id)
                                logger.info(f"🧹 Hapus request {req_id} untuk user {user_id}")
                                
                                if req_id in sent_requests:
                                    del sent_requests[req_id]
                
                waiting_for_result[user_id] = False
            except Exception as e:
                logger.error(f"❌ Gagal hapus queue: {e}")
            
            return True
        else:
            logger.error(f"❌ Gagal kirim ke user {user_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Gagal kirim ke user {user_id}: {e}")
        return False

# ==================== TELEGRAM EVENT HANDLER ====================

@events.register(events.NewMessage)
async def message_handler(event):
    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    text = message.text or message.message or ''
    
    # LOG DETAIL PESAN UNTUK DEBUG
    logger.info("=" * 60)
    logger.info(f"📩 RAW MESSAGE: id={message.id}, chat={chat_id}, sender={sender_id}")
    logger.info(f"📸 Has photo: {bool(message.photo)}")
    logger.info(f"📝 Text: {repr(text)}")
    if message.photo:
        logger.info("📸 INI FOTO CAPTCHA!")
    
    if chat_id != 7240340418 and sender_id != 7240340418:
        logger.info("❌ Bukan dari Bot A, ignore")
        logger.info("=" * 60)
        return
    
    logger.info("🎯 PESAN DARI BOT A DITERIMA!")
    
    # Reset timer untuk request pertama di queue
    req_bytes = r.lindex('pending_requests', 0)
    req_id = None
    if req_bytes:
        req_id = req_bytes.decode('utf-8')
        if req_id in sent_requests:
            sent_requests[req_id]['last_sent'] = time.time()
            logger.info(f"⏱️ Reset timer untuk request {req_id}")
    
    # ===== HASIL INFO =====
    if 'BIND ACCOUNT INFO' in text and 'ID:' in text and 'Server:' in text:
        logger.info("✅ DAPET HASIL INFO!")
        
        # Ambil ID dari text
        id_match = re.search(r'ID:?\s*(\d+)', text)
        server_match = re.search(r'Server:?\s*(\d+)', text)
        
        if id_match and server_match:
            uid = id_match.group(1)
            sid = server_match.group(1)
            
            # Ekstrak data lainnya
            android_match = re.search(r'Android:?\s*(\d+)', text)
            ios_match = re.search(r'iOS:?\s*(\d+)', text)
            
            android = android_match.group(1) if android_match else '0'
            ios = ios_match.group(1) if ios_match else '0'
            
            # Panggil GoPay
            gopay = validate_mlbb_gopay_sync(uid, sid)
            
            if gopay['status']:
                nickname = gopay['username']
                region = gopay['region']
            else:
                nickname = 'Tidak diketahui'
                region = '🌍 Tidak diketahui'
            
            # Format dan kirim
            output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)
            await send_to_bot_b(int(uid), output, markup)
            
            # Hapus dari sent_requests
            if req_id and req_id in sent_requests:
                del sent_requests[req_id]
        
        logger.info("=" * 60)
        return
    
    # ===== RATE LIMIT =====
    if 'please wait' in text.lower() or 'rate limit' in text.lower():
        logger.warning("⏳ RATE LIMIT DARI BOT A! Menunggu 10 detik...")
        
        # Tunggu 10 detik
        await asyncio.sleep(10)
        
        # COBA LAGI request yang sama
        if req_bytes and req_id:
            req_json = r.get(req_id)
            if req_json:
                req_data = json.loads(req_json)
                cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                
                await client.send_message(BOT_A_USERNAME, cmd)
                logger.info(f"🔄 COBA LAGI setelah rate limit: {cmd}")
                
                if req_id in sent_requests:
                    sent_requests[req_id]['last_sent'] = time.time()
                    sent_requests[req_id]['attempts'] += 1
        
        logger.info("=" * 60)
        return
    
    # ===== VERIFIKASI SUKSES =====
    if 'verification successful' in text.lower():
        logger.info("✅ Verifikasi sukses")
        cleanup_downloaded_photos()
        bot_status['in_captcha'] = False
        
        # Delay 5 detik sebelum auto-retry
        logger.info("⏳ Menunggu 5 detik sebelum auto-retry...")
        await asyncio.sleep(5)
        
        # AUTO RETRY: Ambil request pertama dan kirim ulang
        try:
            req_bytes = r.lindex('pending_requests', 0)
            if req_bytes:
                req_id = req_bytes.decode('utf-8')
                req_json = r.get(req_id)
                if req_json:
                    req_data = json.loads(req_json)
                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"🔄 AUTO-RETRY setelah verify: {cmd}")
                    
                    # Update sent_requests
                    if req_id in sent_requests:
                        sent_requests[req_id]['last_sent'] = time.time()
                        sent_requests[req_id]['attempts'] += 1
                    else:
                        sent_requests[req_id] = {
                            'first_sent': time.time(),
                            'last_sent': time.time(),
                            'user_id': req_data['chat_id'],
                            'attempts': 1
                        }
                    
                    waiting_for_result[req_data['chat_id']] = True
        except Exception as e:
            logger.error(f"❌ Gagal auto-retry: {e}")
        
        logger.info("=" * 60)
        return
    
    # ===== CAPTCHA =====
    # Deteksi captcha: foto ATAU teks mengandung captcha + angka ATAU angka 6 digit doang
    if message.photo or ('captcha' in text.lower() and re.search(r'\d{6}', text)) or re.search(r'^\d{6}$', text.strip()):
        logger.warning("🚫 CAPTCHA DETECTED!")
        
        captcha_code = None
        
        # Cek di caption/text
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            captcha_code = ''.join(digits[:6])
            logger.info(f"✅ Captcha code dari text: {captcha_code}")
        
        # Cek dengan OCR (untuk foto)
        if not captcha_code and message.photo and OCR_SPACE_API_KEY:
            logger.info("🔍 Mencoba OCR untuk foto captcha...")
            captcha_code = await read_number_from_photo_online(message)
            if captcha_code:
                logger.info(f"✅ Captcha code dari OCR: {captcha_code}")
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # Set waiting flag untuk user pertama di queue
            req_bytes = r.lindex('pending_requests', 0)
            if req_bytes:
                req_id = req_bytes.decode('utf-8')
                req_json = r.get(req_id)
                if req_json:
                    req_data = json.loads(req_json)
                    waiting_for_result[req_data['chat_id']] = True
                    logger.info(f"📋 Waiting flag SET untuk user {req_data['chat_id']}")
                    
                    # Catat di sent_requests
                    if req_id not in sent_requests:
                        sent_requests[req_id] = {
                            'first_sent': time.time(),
                            'last_sent': time.time(),
                            'user_id': req_data['chat_id'],
                            'attempts': 1
                        }
            
            # Kirim verify (LANGSUNG, TANPA DELAY)
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info(f"📤 Verifikasi dikirim: /verify {captcha_code}")
            
            # Jangan reset bot_status di sini, nanti direset setelah verifikasi sukses
        else:
            logger.error("❌❌❌ Gagal mendapatkan code captcha")
            cleanup_downloaded_photos()
            
            # HAPUS REQUEST PERTAMA KARENA CAPTCHA GAGAL
            req_bytes = r.lindex('pending_requests', 0)
            if req_bytes:
                req_id = req_bytes.decode('utf-8')
                user_id = None
                req_json = r.get(req_id)
                if req_json:
                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                
                r.lpop('pending_requests')
                r.delete(req_id)
                logger.warning(f"🧹 Hapus request {req_id} karena captcha gagal")
                
                if user_id and user_id in waiting_for_result:
                    waiting_for_result[user_id] = False
                
                if req_id in sent_requests:
                    del sent_requests[req_id]
            
            bot_status['in_captcha'] = False
        
        logger.info("=" * 60)
        return
    
    logger.info("❌ Pesan lain dari Bot A - IGNORED")
    logger.info("=" * 60)

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            current_time = time.time()
            
            # CEK REQUEST YANG TIMEOUT
            for req_id, data in list(sent_requests.items()):
                # Total timeout 30 detik sejak pertama dikirim
                if current_time - data['first_sent'] > TOTAL_TIMEOUT:
                    logger.error(f"❌ Request {req_id} TOTAL TIMEOUT {TOTAL_TIMEOUT} DETIK, dihapus")
                    r.lrem('pending_requests', 0, req_id)
                    r.delete(req_id)
                    if data['user_id'] in waiting_for_result:
                        waiting_for_result[data['user_id']] = False
                    del sent_requests[req_id]
                    continue
                
                # Response timeout 15 detik
                if current_time - data['last_sent'] > TIMEOUT:
                    logger.warning(f"⏰ Request {req_id} timeout {TIMEOUT} detik, attempt {data['attempts']}")
                    
                    if data['attempts'] >= MAX_ATTEMPTS:
                        logger.error(f"❌ Request {req_id} gagal setelah {MAX_ATTEMPTS}x percobaan")
                        r.lrem('pending_requests', 0, req_id)
                        r.delete(req_id)
                        if data['user_id'] in waiting_for_result:
                            waiting_for_result[data['user_id']] = False
                        del sent_requests[req_id]
                    else:
                        # Kirim ulang
                        req_json = r.get(req_id)
                        if req_json:
                            req_data = json.loads(req_json)
                            cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                            
                            await client.send_message(BOT_A_USERNAME, cmd)
                            logger.info(f"🔄 PERCOBAAN KE-{data['attempts']+1}: {cmd}")
                            
                            data['attempts'] += 1
                            data['last_sent'] = current_time
            
            # Cek apakah ada yang sedang diproses
            processing = any(waiting for waiting in waiting_for_result.values())
            
            # Jika tidak ada yang diproses, ambil request berikutnya
            if not processing and not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    
                    # Cek apakah request ini sudah pernah dikirim
                    if req_id in sent_requests:
                        await asyncio.sleep(1)
                        continue
                    
                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests')
                        continue
                    
                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                    
                    # Cek apakah user sedang menunggu hasil
                    if waiting_for_result.get(user_id, False):
                        logger.info(f"⏳ User {user_id} menunggu hasil, tunda...")
                        await asyncio.sleep(2)
                        continue
                    
                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Kirim: {cmd}")
                    
                    # Catat request yang dikirim
                    sent_requests[req_id] = {
                        'first_sent': current_time,
                        'last_sent': current_time,
                        'user_id': user_id,
                        'attempts': 1
                    }
                    waiting_for_result[user_id] = True
                    
        except Exception as e:
            logger.error(f"❌ Queue error: {e}")
        
        await asyncio.sleep(2)

# ==================== MAIN ====================

async def main():
    logger.info("🚀 Starting Telethon userbot...")
    logger.info(f"🔗 Stok Admin URL: {STOK_ADMIN_URL}")
    
    # Bersihkan queue lama
    try:
        queue_len = r.llen('pending_requests')
        if queue_len > 0:
            logger.info(f"🧹 Membersihkan {queue_len} request lama dari queue...")
            for _ in range(queue_len):
                r.lpop('pending_requests')
        
        keys = r.keys('req:*')
        if keys:
            logger.info(f"🧹 Membersihkan {len(keys)} request data lama...")
            for key in keys:
                r.delete(key)
        
        # Reset state
        global sent_requests, waiting_for_result
        sent_requests = {}
        waiting_for_result = {}
        
        logger.info("✅ Queue bersih! Siap menerima request baru.")
        
    except Exception as e:
        logger.error(f"❌ Gagal bersihkan queue: {e}")
    
    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Login sebagai: {me.first_name}")
        
        client.add_event_handler(message_handler)
        logger.info("✅ Event handler registered")
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
