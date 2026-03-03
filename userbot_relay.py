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
from PIL import Image, ImageEnhance

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
BOT_A_USERNAME = 'bengkelmlbb_bot'  # PAKAI USERNAME, BUKAN ID
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')

# Country mapping (5 negara)
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
            "userId": str(user_id),
            "zoneId": str(server_id)
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result and result.get('data'):
                v = result['data']
                
                # Proses username
                username = v.get('username', 'Unknown')
                username = username.replace('+', ' ')
                
                # Proses region
                country = v.get('countryOrigin', 'ID').upper()
                region = country_mapping.get(country, f'🌍 {country}')
                
                return {
                    'status': True,
                    'creator': 'AntiDEV',
                    'result': {
                        'userId': user_id,
                        'serverId': server_id,
                        'username': username,
                        'region': region
                    }
                }
        
        return {
            'status': False,
            'creator': 'AntiDEV',
            'message': 'Invalid UserId or ServerId'
        }
        
    except Exception as e:
        logger.error(f"❌ GoPay API error: {e}")
        return {
            'status': False,
            'creator': 'AntiDEV',
            'message': str(e)
        }

# ==================== OCR ONLINE FUNCTION ====================

async def read_number_from_photo_online(message):
    """Baca angka 6 digit dari foto captcha menggunakan OCR.space API"""
    try:
        if not OCR_SPACE_API_KEY:
            logger.error("❌ OCR_SPACE_API_KEY tidak tersedia")
            return None
        
        logger.info("📸 OCR Online: Downloading captcha photo...")
        
        # Download foto
        photo_path = await message.download_media()
        logger.info(f"✅ Photo downloaded: {photo_path}")
        
        # Baca file sebagai base64
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Hapus file setelah dibaca
        os.remove(photo_path)
        
        # OCR.space API endpoint
        url = 'https://api.ocr.space/parse/image'
        
        # Payload untuk API
        payload = {
            'base64Image': f'data:image/jpeg;base64,{image_data}',
            'apikey': OCR_SPACE_API_KEY,
            'language': 'eng',
            'OCREngine': '2',
            'isTable': 'false',
            'scale': 'true',
            'detectOrientation': 'true'
        }
        
        logger.info("📤 Sending to OCR.space API...")
        
        # Kirim request
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('IsErroredOnProcessing') == False:
                if result.get('ParsedResults') and len(result['ParsedResults']) > 0:
                    text = result['ParsedResults'][0].get('ParsedText', '')
                    
                    # Bersihkan hasil (ambil hanya angka)
                    text = re.sub(r'[^0-9]', '', text)
                    logger.info(f"📝 OCR result: '{text}'")
                    
                    # Cari 6 digit
                    match = re.search(r'(\d{6})', text)
                    if match:
                        code = match.group(1)
                        logger.info(f"✅ OCR Online success: {code}")
                        return code
                    else:
                        logger.warning("❌ No 6-digit found in OCR result")
            else:
                error = result.get('ErrorMessage', ['Unknown error'])[0]
                logger.error(f"❌ OCR Error: {error}")
        else:
            logger.error(f"❌ API Error: {response.status_code}")
            
        return None
        
    except Exception as e:
        logger.error(f"❌ OCR Online error: {e}")
        return None

# ==================== FUNGSI FORMAT OUTPUT ====================

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    """Format output final sesuai permintaan"""
    
    # Ekstrak bind info dari text asli
    bind_lines = []
    lines = original_text.split('\n')
    
    for line in lines:
        if any(keyword in line for keyword in ['Moonton', 'Google Play', 'Facebook', 'Tiktok', 'VK', 'Apple', 'GCID', 'Telegram', 'WhatsApp']):
            # Bersihkan format
            clean_line = line.replace('✧', '•').strip()
            # Hapus spasi berlebih
            clean_line = re.sub(r'\s+', ' ', clean_line)
            bind_lines.append(clean_line)
    
    # Gabungkan bind info
    bind_info = '\n'.join(bind_lines) if bind_lines else '• Data bind tidak tersedia'
    
    # Format final
    final = f"""INFORMASI AKUN

ID: {uid}
Server: {sid}
Nickname: {nickname}
Region: {region}

BIND INFO:
{bind_info}

Device Login:
• Android: {android} perangkat
• iOS: {ios} perangkat"""
    
    return final

# ==================== RETRY PENDING REQUESTS ====================

async def retry_pending_requests():
    """Kirim ulang request yang pending setelah captcha selesai"""
    logger.info("🔄 Retrying pending requests...")
    
    retry_count = 0
    while True:
        request_id = r.lpop('pending_requests')
        if not request_id:
            break
            
        request_id = request_id.decode('utf-8')
        request_data_json = r.get(request_id)
        
        if request_data_json is None:
            continue
        
        request_data = json.loads(request_data_json)
        cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
        
        # PAKAI USERNAME, BUKAN ID
        await client.send_message(BOT_A_USERNAME, cmd)
        logger.info(f"🔄 Retry: {cmd} for user {request_data['chat_id']}")
        
        r.setex(request_id, 300, json.dumps(request_data))
        retry_count += 1
        await asyncio.sleep(1)
    
    if retry_count > 0:
        logger.info(f"✅ Retried {retry_count} requests")

# ==================== TELEGRAM EVENT HANDLER ====================

@events.register(events.NewMessage)
async def message_handler(event):
    """
    Handler untuk semua pesan baru
    """
    message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id
    
    # Ambil teks
    text = message.text or message.message or ''
    
    # LOG LENGKAP
    logger.info("=" * 80)
    logger.info("🔥🔥🔥 TELETHON MESSAGE HANDLER 🔥🔥🔥")
    logger.info(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📌 Message ID: {message.id}")
    logger.info(f"💬 Chat ID: {chat_id}")
    logger.info(f"👤 Sender ID: {sender_id}")
    logger.info(f"📸 Has Photo: {bool(message.photo)}")
    logger.info(f"📝 Text preview: '{text[:100]}'")
    
    # CEK APAKAH DARI BOT A (gunakan ID)
    if chat_id != 7240340418 and sender_id != 7240340418:
        logger.info("❌ Bukan dari Bot A")
        logger.info("=" * 80)
        return
    
    logger.info("🎯🎯🎯 PESAN DARI BOT A DITERIMA!")
    
    # ===== CEK APAKAH INI HASIL INFO VALID =====
    if 'BIND ACCOUNT INFO' in text or 'INFORMASI AKUN' in text or '──────────────────────' in text:
        logger.info("✅✅✅ INI HASIL INFO VALID! FORWARDING KE USER...")
        
        # Ambil request dari queue
        request_id = r.lpop('pending_requests')
        
        if request_id:
            request_id = request_id.decode('utf-8')
            request_data_json = r.get(request_id)
            
            if request_data_json is None:
                logger.warning(f"⚠️ Request expired")
                logger.info("=" * 80)
                return
            
            request_data = json.loads(request_data_json)
            user_id = request_data['chat_id']
            
            # Ekstrak ID dan Server dari text
            id_match = re.search(r'ID:?\s*(\d+)', text)
            server_match = re.search(r'Server:?\s*(\d+)', text)
            
            # Ekstrak device login
            android_match = re.search(r'Android:?\s*(\d+)', text)
            ios_match = re.search(r'iOS:?\s*(\d+)', text)
            
            uid = id_match.group(1) if id_match else 'Unknown'
            sid = server_match.group(1) if server_match else 'Unknown'
            android = android_match.group(1) if android_match else '0'
            ios = ios_match.group(1) if ios_match else '0'
            
            # Panggil API GoPay
            gopay_result = validate_mlbb_gopay_sync(uid, sid)
            
            if gopay_result['status']:
                nickname = gopay_result['result']['username']
                region = gopay_result['result']['region']
                logger.info(f"✅ GoPay: {nickname} - {region}")
            else:
                nickname = 'Tidak diketahui'
                region = '🌍 Tidak diketahui'
                logger.warning(f"⚠️ GoPay: {gopay_result.get('message')}")
            
            # Format output final
            final_output = format_final_output(text, nickname, region, uid, sid, android, ios)
            
            # Kirim ke user via Bot B
            url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
            data = {
                'chat_id': user_id,
                'text': final_output,
                'parse_mode': 'HTML'
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅✅✅ TERKIRIM KE USER {user_id}!")
                    r.delete(request_id)
                    
                    # Reset state
                    if user_id in waiting_for_result:
                        waiting_for_result[user_id] = False
                else:
                    logger.error(f"❌ Gagal forward: {response.status_code}")
                    r.rpush('pending_requests', request_id)
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
                r.rpush('pending_requests', request_id)
        else:
            logger.warning("⚠️ TIDAK ADA REQUEST PENDING!")
        
        logger.info("=" * 80)
        return
    
    # ===== CEK APAKAH INI PESAN VERIFIKASI SUKSES =====
    if text and ('verification successful' in text.lower() or 'verified' in text.lower()):
        logger.info("✅ Captcha verification successful - IGNORED")
        logger.info("=" * 80)
        return
    
    # ===== CEK APAKAH INI PESAN RATE LIMIT =====
    if 'please wait' in text.lower() or 'rate limit' in text.lower():
        logger.warning("⏳ RATE LIMIT DARI BOT A! Menunggu 30 detik...")
        await asyncio.sleep(30)
        logger.info("✅ Selesai menunggu rate limit")
        logger.info("=" * 80)
        return
    
    # ===== CEK CAPTCHA =====
    is_captcha = False
    captcha_code = None
    
    # Cek 1: Ada foto (captcha)
    if message.photo:
        logger.info("📸 PHOTO DETECTED - This is a captcha")
        is_captcha = True
        
        # SET STATE untuk user yang menunggu
        top_request = r.lindex('pending_requests', 0)
        if top_request:
            top_req_id = top_request.decode('utf-8')
            top_req_data = json.loads(r.get(top_req_id))
            waiting_user = top_req_data['chat_id']
            waiting_for_result[waiting_user] = True
            logger.info(f"📋 Waiting for result SET for user {waiting_user}")
        
        # Cek angka di caption
        if text:
            digits = re.findall(r'\d', text)
            if len(digits) >= 6:
                captcha_code = ''.join(digits[:6])
                logger.info(f"✅ Found code in caption: {captcha_code}")
    
    # Cek 2: Teks mengandung angka 6 digit + kata kunci
    if not is_captcha and text:
        digits = re.findall(r'\d', text)
        if len(digits) >= 6:
            keywords = ['captcha', 'verify', 'code', 'enter', 'kode']
            if any(kw in text.lower() for kw in keywords):
                is_captcha = True
                captcha_code = ''.join(digits[:6])
                logger.info(f"✅ Found code in text: {captcha_code}")
                
                top_request = r.lindex('pending_requests', 0)
                if top_request:
                    top_req_id = top_request.decode('utf-8')
                    top_req_data = json.loads(r.get(top_req_id))
                    waiting_user = top_req_data['chat_id']
                    waiting_for_result[waiting_user] = True
                    logger.info(f"📋 Waiting for result SET for user {waiting_user}")
    
    # ===== JIKA CAPTCHA =====
    if is_captcha:
        logger.warning("🚫 CAPTCHA PROCESSING...")
        
        # Jika captcha_code belum ada, pakai OCR
        if not captcha_code and message.photo:
            logger.info("🔍 No text code, trying OCR...")
            captcha_code = await read_number_from_photo_online(message)
        
        if captcha_code and len(captcha_code) == 6:
            logger.info(f"✅✅✅ CAPTCHA CODE: {captcha_code}")
            bot_status['in_captcha'] = True
            
            # PAKAI USERNAME UNTUK VERIFY
            await client.send_message(BOT_A_USERNAME, f"/verify {captcha_code}")
            logger.info(f"📤 Verification sent: /verify {captcha_code}")
            
            await asyncio.sleep(2)
            bot_status['in_captcha'] = False
            
            await retry_pending_requests()
        else:
            logger.error("❌❌❌ Gagal mendapatkan captcha code")
            await asyncio.sleep(30)
            bot_status['in_captcha'] = False
        
        logger.info("=" * 80)
        return
    
    logger.info("❌ Pesan lain dari Bot A - IGNORED")
    logger.info("=" * 80)

@events.register(events.MessageEdited)
async def message_edit_handler(event):
    logger.info(f"✏️ Message edited in chat {event.chat_id}")

# ==================== QUEUE PROCESSOR ====================

async def process_queue():
    logger.info("🔄 Queue processor started")
    
    while True:
        try:
            queue_length = r.llen('pending_requests')
            if queue_length > 0:
                logger.info(f"📊 Queue length: {queue_length}")
            
            if not bot_status['in_captcha'] and queue_length > 0:
                request_id_bytes = r.lindex('pending_requests', 0)
                
                if request_id_bytes:
                    request_id = request_id_bytes.decode('utf-8')
                    current_time = time.time()
                    
                    if request_id in sent_requests:
                        last_sent = sent_requests[request_id]
                        time_diff = current_time - last_sent
                        
                        if time_diff < 15:
                            await asyncio.sleep(2)
                            continue
                    
                    request_data_json = r.get(request_id)
                    if request_data_json is None:
                        r.lpop('pending_requests')
                        continue
                    
                    request_data = json.loads(request_data_json)
                    cmd = f"{request_data['command']} {request_data['args'][0]} {request_data['args'][1]}"
                    
                    try:
                        # PAKAI USERNAME, BUKAN ID - LANGSUNG KERJA TANPA PERLU CHAT DULUAN
                        await client.send_message(BOT_A_USERNAME, cmd)
                        logger.info(f"📤 Sent to Bot A: {cmd}")
                        sent_requests[request_id] = current_time
                    except Exception as e:
                        logger.error(f"❌ Failed to send to Bot A: {e}")
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
        
        await asyncio.sleep(2)

# ==================== MAIN ====================

async def main():
    global sent_requests, waiting_for_result
    sent_requests = {}
    waiting_for_result = {}
    
    logger.info("🚀 Starting Telethon userbot...")
    
    try:
        await client.start()
        logger.info("✅ Telethon client started!")
        
        me = await client.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        
        # TIDAK PERLU RESOLVE ENTITY - LANGSUNG PAKAI USERNAME NANTI
        
        client.add_event_handler(message_handler)
        client.add_event_handler(message_edit_handler)
        logger.info("✅ Event handlers registered")
        
        await process_queue()
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
