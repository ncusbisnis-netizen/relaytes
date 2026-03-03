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

# Country mapping sederhana
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
sent_requests = {}
waiting_for_result = {}
downloaded_photos = []

# ==================== FUNGSI VALIDASI GOPAY ====================

def validate_mlbb_gopay_sync(user_id, server_id):
    """Validasi akun MLBB menggunakan API GoPay"""
    url = 'https://gopay.co.id/games/v1/order/user-account'
    
    headers = {
        'Content-Type': 'application/json',
        'X-Client': 'web-mobile',
        'X-Timestamp': str(int(time.time() * 1000)),
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
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
        
        response = requests.post(
            url, 
            headers=headers, 
            json=body,
            timeout=30
        )
        
        logger.info(f"📥 Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP Error {response.status_code}")
            return {
                'status': False,
                'message': f'HTTP {response.status_code}'
            }
        
        result = response.json()
        
        if not result or 'data' not in result:
            logger.error(f"❌ Invalid response structure")
            return {'status': False, 'message': 'Invalid response'}
        
        data = result['data']
        
        username = data.get('username', 'Unknown')
        if username:
            username = username.replace('+', ' ')
        
        country = data.get('countryOrigin', 'ID')
        if country:
            country = country.upper()
        
        region = country_mapping.get(country, f'🌍 {country}')
        
        logger.info(f"✅ GoPay SUCCESS: {username} - {region}")
        
        return {
            'status': True,
            'username': username,
            'region': region
        }
        
    except requests.exceptions.Timeout:
        logger.error("❌ REQUEST TIMEOUT!")
        return {'status': False, 'message': 'Request timeout'}
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {'status': False, 'message': str(e)}

# ==================== OCR ONLINE FUNCTION ====================

async def read_number_from_photo_online(message):
    """Baca angka 6 digit dari foto captcha menggunakan OCR.space API"""
    try:
        if not OCR_SPACE_API_KEY:
            return None
        
        logger.info("📸 Downloading captcha photo...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        url = 'https://api.ocr.space/parse/image'
        payload = {
            'base64Image': f'data:image/jpeg;base64,{image_data}',
            'apikey': OCR_SPACE_API_KEY,
            'language': 'eng',
            'OCREngine': '2'
        }
        
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if not result.get('IsErroredOnProcessing'):
                if result.get('ParsedResults'):
                    text = result['ParsedResults'][0].get('ParsedText', '')
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
    """Hapus semua foto yang sudah didownload"""
    global downloaded_photos
    
    for photo_path in downloaded_photos[:]:
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
            downloaded_photos.remove(photo_path)
        except:
            pass

# ==================== FORMAT OUTPUT DENGAN TOMBOL ====================

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    """Format output final dengan tombol Stok Admin"""
    
    # Ambil bind info (hanya yang tidak empty)
    bind_lines = []
    lines = original_text.split('\n')
    
    keywords = ['Moonton', 'Google Play', 'Facebook', 'Tiktok', 'VK', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    
    for line in lines:
        for kw in keywords:
            if kw in line and 'empty' not in line.lower():
                clean_line = line.replace('✧', '•').strip()
                clean_line = re.sub(r'\s+', ' ', clean_line)
                bind_lines.append(clean_line)
                break
    
    bind_info = '\n'.join(bind_lines) if bind_lines else '• Tidak ada data bind'
    
    # Format teks
    text = f"""INFORMASI AKUN

ID: {uid}
Server: {sid}
Nickname: {nickname}
Region: {region}

BIND INFO:
{bind_info}

Device Login:
• Android: {android} perangkat
• iOS: {ios} perangkat"""

    # Tombol inline
    reply_markup = {
        'inline_keyboard': [
            [{'text': 'STOK ADMIN', 'url': STOK_ADMIN_URL}]
        ]
    }
    
    return text, reply_markup

# ==================== SEND TO BOT B ====================

async def send_to_bot_b(user_id, text, reply_markup=None):
    """Kirim pesan ke user via Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': user_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ TERKIRIM KE USER {user_id}")
            return True
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
    
    # Hanya pesan dari Bot A
    if chat_id != 7240340418 and sender_id != 7240340418:
        return
    
    logger.info(f"📩 Pesan dari Bot A: {text[:100]}")
    
    # ===== HASIL INFO VALID =====
    if 'BIND ACCOUNT INFO' in text or 'INFORMASI AKUN' in text:
        logger.info("✅ DAPET HASIL INFO!")
        
        # Cari user yang menunggu
        target_user = None
        for uid, waiting in list(waiting_for_result.items()):
            if waiting:
                target_user = uid
                break
        
        if not target_user:
            # Fallback ke queue
            req_bytes = r.lindex('pending_requests', 0)
            if req_bytes:
                req_id = req_bytes.decode('utf-8')
                req_json = r.get(req_id)
                if req_json:
                    req_data = json.loads(req_json)
                    target_user = req_data['chat_id']
                    r.lpop('pending_requests')
                    r.delete(req_id)
        
        if target_user:
            # Extract data
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
            
            # Format dan kirim
            output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)
            await send_to_bot_b(target_user, output, markup)
            
            # Reset flag
            if target_user in waiting_for_result:
                waiting_for_result[target_user] = False
        
        return
    
    # ===== VERIFIKASI SUKSES =====
    if 'verification successful' in text.lower() or 'verified' in text.lower():
        logger.info("✅ Verifikasi sukses")
        cleanup_downloaded_photos()
        return
    
    # ===== RATE LIMIT =====
    if 'please wait' in text.lower() or 'rate limit' in text.lower():
        logger.warning("⏳ Rate limit, tunggu 30 detik")
        await asyncio.sleep(30)
        return
    
    # ===== CAPTCHA =====
    is_captcha = False
    captcha_code = None
    
    # Cek photo
    if message.photo:
        is_captcha = True
        
        # Set waiting flag
        top_req = r.lindex('pending_requests', 0)
        if top_req:
            top_id = top_req.decode('utf-8')
            top_data = json.loads(r.get(top_id))
            waiting_for_result[top_data['chat_id']] = True
        
        # Cek angka di caption
        if text:
            digits = re.findall(r'\d', text)
            if len(digits) >= 6:
                captcha_code = ''.join(digits[:6])
    
    # Cek text
    if not is_captcha and text:
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            keywords = ['captcha', 'verify', 'code', 'enter', 'kode']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = ''.join(digits[:6])
                
                top_req = r.lindex('pending_requests', 0)
                if top_req:
                    top_id = top_req.decode('utf-8')
                    top_data = json.loads(r.get(top_id))
                    waiting_for_result[top_data['chat_id']] = True
    
    # Proses captcha
    if is_captcha:
        logger.warning("🚫 CAPTCHA DETECTED!")
        
        if not captcha_code and message.photo:
            captcha_code = await read_number_from_photo_online(message)
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅ Code: {captcha_code}")
            bot_status['in_captcha'] = True
            
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info(f"📤 Verifikasi dikirim")
            
            await asyncio.sleep(5)
            bot_status['in_captcha'] = False
            
            # TIDAK RETRY! Langsung tunggu hasil
            logger.info("⏳ Menunggu hasil...")
        else:
            logger.error("❌ Gagal dapat code")
            cleanup_downloaded_photos()
            await asyncio.sleep(30)
            bot_status['in_captcha'] = False

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            q_len = r.llen('pending_requests')
            
            if not bot_status['in_captcha'] and q_len > 0:
                req_bytes = r.lindex('pending_requests', 0)
                
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now = time.time()
                    
                    # Cek rate limit
                    if req_id in sent_requests:
                        if now - sent_requests[req_id] < 15:
                            await asyncio.sleep(2)
                            continue
                    
                    req_json = r.get(req_id)
                    if not req_json:
                        r.lpop('pending_requests')
                        continue
                    
                    req_data = json.loads(req_json)
                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Kirim: {cmd}")
                    
                    sent_requests[req_id] = now
                    waiting_for_result[req_data['chat_id']] = True
                    
        except Exception as e:
            logger.error(f"❌ Queue error: {e}")
        
        await asyncio.sleep(2)

# ==================== MAIN ====================

async def main():
    logger.info("🚀 Starting Telethon userbot...")
    
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
