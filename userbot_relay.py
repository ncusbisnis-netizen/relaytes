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

# Country mapping lengkap
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
sent_requests = {}
waiting_for_result = {}
downloaded_photos = []

MAX_ATTEMPTS = 3
TIMEOUT = 15
TOTAL_TIMEOUT = 30

# ==================== FUNGSI CLEANUP TEXT ====================

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

# ==================== FUNGSI VALIDASI GOPAY ====================

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
        logger.info(f"📤 GoPay Request: {user_id}:{server_id}")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        logger.info(f"📥 Response status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            return {'status': False, 'message': f'HTTP {response.status_code}'}
        
        result = response.json()
        data = result.get('data', {})
        username = data.get('username', 'Unknown').replace('+', ' ')
        country = data.get('countryOrigin', 'ID').upper()
        region = country_mapping.get(country, f'🌍 {country}')
        
        logger.info(f"✅ GoPay SUCCESS: {username} - {region}")
        return {'status': True, 'username': username, 'region': region}
        
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

# ==================== CLEANUP PHOTOS ====================

def cleanup_downloaded_photos():
    global downloaded_photos
    for photo_path in downloaded_photos[:]:
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
            downloaded_photos.remove(photo_path)
        except:
            pass

# ==================== FORMAT OUTPUT ====================

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    keywords = ['Moonton', 'VK', 'Google Play', 'Tiktok', 'Facebook', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    bind_info = []
    
    for kw in keywords:
        found = False
        for line in original_text.split('\n'):
            if kw in line:
                clean_line = line.replace('✧', '•').strip()
                clean_line = re.sub(r'\s+', ' ', clean_line)
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

async def send_to_bot_b(telegram_user_id, text, reply_markup=None):
    # AMBIL CHAT ID DARI REDIS
    chat_id_key = f"user_chat:{telegram_user_id}"
    chat_id_bytes = r.get(chat_id_key)
    
    if not chat_id_bytes:
        logger.error(f"❌ Chat ID untuk telegram user {telegram_user_id} tidak ditemukan!")
        return False
    
    chat_id = int(chat_id_bytes.decode('utf-8'))
    
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        logger.info(f"📤 Mengirim ke telegram user {telegram_user_id} (chat_id: {chat_id})...")
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ TERKIRIM KE USER {telegram_user_id}")
            return True
        else:
            logger.error(f"❌ Gagal kirim: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Gagal kirim: {e}")
        return False

# ==================== TELEGRAM EVENT HANDLER ====================

@events.register(events.NewMessage)
async def message_handler(event):
    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    text = message.text or message.message or ''
    
    logger.info("=" * 60)
    logger.info(f"📩 RAW MESSAGE: id={message.id}, chat={chat_id}, sender={sender_id}")
    logger.info(f"📸 Has photo: {bool(message.photo)}")
    logger.info(f"📝 Text: {repr(text)[:200]}")
    
    if chat_id != 7240340418 and sender_id != 7240340418:
        logger.info("❌ Bukan dari Bot A")
        logger.info("=" * 60)
        return
    
    logger.info("🎯 PESAN DARI BOT A DITERIMA!")
    
    # Ambil request pertama dari queue
    req_bytes = r.lindex('pending_requests', 0)
    req_id = None
    request_data = None
    
    if req_bytes:
        req_id = req_bytes.decode('utf-8')
        req_json = r.get(req_id)
        if req_json:
            request_data = json.loads(req_json)
            if req_id in sent_requests:
                sent_requests[req_id]['last_sent'] = time.time()
                logger.info(f"⏱️ Reset timer untuk request {req_id}")
    
    # ===== HASIL INFO =====
    if 'BIND ACCOUNT INFO' in text and 'ID:' in text and 'Server:' in text:
        logger.info("✅ DAPET HASIL INFO!")
        
        if request_data:
            telegram_user_id = request_data['telegram_user_id']  # <-- INI YANG DIPAKAI!
            logger.info(f"🎯 Target telegram user: {telegram_user_id}")
            
            # Ekstrak data dari hasil Bot A
            id_match = re.search(r'ID:?\s*(\d+)', text)
            server_match = re.search(r'Server:?\s*(\d+)', text)
            android_match = re.search(r'Android:?\s*(\d+)', text)
            ios_match = re.search(r'iOS:?\s*(\d+)', text)
            
            uid = id_match.group(1) if id_match else 'Unknown'
            sid = server_match.group(1) if server_match else 'Unknown'
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
            
            # Format dan kirim ke TELEGRAM USER ID
            output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)
            await send_to_bot_b(telegram_user_id, output, markup)
            
            # Hapus request dari queue
            r.lpop('pending_requests')
            r.delete(req_id)
            if req_id in sent_requests:
                del sent_requests[req_id]
            if telegram_user_id in waiting_for_result:
                waiting_for_result[telegram_user_id] = False
        
        logger.info("=" * 60)
        return
    
    # ===== RATE LIMIT =====
    if 'please wait' in text.lower() or 'rate limit' in text.lower():
        logger.warning("⏳ RATE LIMIT! Menunggu 10 detik...")
        await asyncio.sleep(10)
        
        if request_data:
            cmd = f"{request_data['command']} {request_data['mlbb_id']} {request_data.get('server_id', '')}"
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 COBA LAGI: {cmd}")
        
        logger.info("=" * 60)
        return
    
    # ===== VERIFIKASI SUKSES =====
    if 'verification successful' in text.lower():
        logger.info("✅ Verifikasi sukses")
        cleanup_downloaded_photos()
        bot_status['in_captcha'] = False
        
        await asyncio.sleep(5)
        
        if request_data:
            cmd = f"{request_data['command']} {request_data['mlbb_id']} {request_data.get('server_id', '')}"
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 AUTO-RETRY: {cmd}")
        
        logger.info("=" * 60)
        return
    
    # ===== CAPTCHA =====
    if message.photo or re.search(r'\d{6}', text):
        logger.warning("🚫 CAPTCHA DETECTED!")
        
        captcha_code = None
        digits = re.findall(r'\d{6}', text)
        if digits:
            captcha_code = digits[0]
            logger.info(f"✅ Captcha code dari text: {captcha_code}")
        
        if not captcha_code and message.photo and OCR_SPACE_API_KEY:
            captcha_code = await read_number_from_photo_online(message)
            if captcha_code:
                logger.info(f"✅ Captcha code dari OCR: {captcha_code}")
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info(f"📤 Verifikasi dikirim")
            
        else:
            logger.error("❌ Gagal dapat code captcha")
            cleanup_downloaded_photos()
            bot_status['in_captcha'] = False
        
        logger.info("=" * 60)
        return
    
    logger.info("❌ Pesan lain - IGNORED")
    logger.info("=" * 60)

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            current_time = time.time()
            
            # Cek timeout
            for req_id, data in list(sent_requests.items()):
                if current_time - data['first_sent'] > TOTAL_TIMEOUT:
                    logger.error(f"❌ Request {req_id} TOTAL TIMEOUT")
                    r.lrem('pending_requests', 0, req_id)
                    r.delete(req_id)
                    if data['user_id'] in waiting_for_result:
                        waiting_for_result[data['user_id']] = False
                    del sent_requests[req_id]
                    continue
                
                if current_time - data['last_sent'] > TIMEOUT:
                    if data['attempts'] >= MAX_ATTEMPTS:
                        logger.error(f"❌ Request {req_id} MAX ATTEMPTS")
                        r.lrem('pending_requests', 0, req_id)
                        r.delete(req_id)
                        if data['user_id'] in waiting_for_result:
                            waiting_for_result[data['user_id']] = False
                        del sent_requests[req_id]
                    else:
                        req_json = r.get(req_id)
                        if req_json:
                            req_data = json.loads(req_json)
                            cmd = f"{req_data['command']} {req_data['mlbb_id']} {req_data.get('server_id', '')}"
                            await client.send_message(BOT_A_USERNAME, cmd)
                            logger.info(f"🔄 PERCOBAAN KE-{data['attempts']+1}: {cmd}")
                            data['attempts'] += 1
                            data['last_sent'] = current_time
            
            # Proses queue
            processing = any(waiting for waiting in waiting_for_result.values())
            
            if not processing and not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    
                    if req_id in sent_requests:
                        await asyncio.sleep(1)
                        continue
                    
                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests')
                        continue
                    
                    req_data = json.loads(req_json)
                    telegram_user_id = req_data['telegram_user_id']
                    
                    if waiting_for_result.get(telegram_user_id, False):
                        logger.info(f"⏳ User {telegram_user_id} menunggu hasil")
                        await asyncio.sleep(2)
                        continue
                    
                    cmd = f"{req_data['command']} {req_data['mlbb_id']} {req_data.get('server_id', '')}"
                    
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Kirim: {cmd}")
                    
                    sent_requests[req_id] = {
                        'first_sent': current_time,
                        'last_sent': current_time,
                        'user_id': telegram_user_id,
                        'attempts': 1
                    }
                    waiting_for_result[telegram_user_id] = True
                    
        except Exception as e:
            logger.error(f"❌ Queue error: {e}")
        
        await asyncio.sleep(2)

# ==================== MAIN ====================

async def main():
    logger.info("🚀 Starting Telethon userbot...")
    
    # Bersihkan queue lama
    try:
        queue_len = r.llen('pending_requests')
        if queue_len > 0:
            logger.info(f"🧹 Membersihkan {queue_len} request lama")
            for _ in range(queue_len):
                r.lpop('pending_requests')
        
        keys = r.keys('req:*')
        if keys:
            for key in keys:
                r.delete(key)
    except Exception as e:
        logger.error(f"❌ Gagal bersihkan queue: {e}")
    
    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Login sebagai: {me.first_name}")
        
        client.add_event_handler(message_handler)
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
