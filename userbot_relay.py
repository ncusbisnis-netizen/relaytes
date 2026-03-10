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

# ==================== KONFIGURASI ====================
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')
BOT_B_TOKEN = os.environ.get('BOT_B_TOKEN', '')
BOT_A_USERNAME = 'bengkelmlbb_bot'
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY', '')
STOK_ADMIN_URL = os.environ.get('STOK_ADMIN_URL', 'https://whatsapp.com/channel/0029VbA4PrD5fM5TMgECoE1E')

# ==================== COUNTRY MAPPING SEDERHANA ====================
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
sent_requests = {}          # untuk rate limiting
waiting_for_result = {}     # flag per user
downloaded_photos = []       # untuk cleanup file OCR

# Data request yang sedang aktif (hanya satu dalam satu waktu)
active_requests = {}        # key: req_id, value: dict {chat_id, message_id, start_time, command, args}

# Timer untuk captcha (agar tidak stuck selamanya)
captcha_timer_task = None

# Konstanta timeout
REQUEST_TIMEOUT = 30
CAPTCHA_TIMEOUT = 30

# ==================== FUNGSI BANTUAN ====================
def clean_bind_text(text):
    """Bersihkan text bind info"""
    # 1. Handle (Private) dan variasinya
    text = re.sub(r'\(Private\)', 'Hide information', text)
    text = re.sub(r'Bind \(Private\)', 'Hide information', text)
    text = re.sub(r'Private', 'Hide information', text)
    
    # 2. Handle Moonton Unverified (khusus Moonton)
    if 'Moonton Unverified' in text:
        parts = text.split('Moonton :', 1)
        if len(parts) > 1:
            text = f"{parts[0]}Moonton : empty."
    
    # 3. Handle (Unverified) untuk yang lain
    text = re.sub(r'\(Unverified\)', 'Failed Verification', text)
    text = re.sub(r'Unverified', 'Failed Verification', text)
    
    # Bersihkan spasi berlebih
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

# ============ TAMBAHKAN FUNGSI INI DI SINI ============
def clean_bind_text(text):
    """Bersihkan text bind info"""
    
    # Handle (Private) dan variasinya
    if 'Private' in text:
        text = re.sub(r'Bind\s*\(Private\)', 'Hide information', text)
        text = re.sub(r'\(Private\)', 'Hide information', text)
        text = re.sub(r'\bPrivate\b', 'Hide information', text)
    
    # Handle (Unverified) - hapus saja
    text = re.sub(r'\s*\(Unverified\)', '', text)
    
    # Handle kasus "Moonton Unverified" (tanpa kurung)
    if 'Moonton Unverified' in text:
        # Jika sudah ada format "Moonton : something"
        if 'Moonton :' in text or 'Moonton:' in text:
            text = re.sub(r'Moonton\s*:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
            text = re.sub(r'Moonton:\s*Moonton\s+Unverified', 'Moonton: empty.', text)
        else:
            text = re.sub(r'Moonton\s+Unverified', 'Moonton: empty.', text)
    
    # CEK KHUSUS: Jika teks mengandung "empty" dan "Moonton" dua kali
    if 'empty' in text.lower() and text.count('Moonton') > 1:
        # Ambil hanya satu "Moonton" sebelum "empty"
        parts = text.split('empty', 1)
        # Cari bagian sebelum empty yang mengandung Moonton
        before_empty = parts[0]
        if 'Moonton' in before_empty:
            # Ambil Moonton terakhir sebelum empty
            moonton_parts = before_empty.split('Moonton')
            if len(moonton_parts) > 1:
                # Gunakan Moonton yang terakhir
                text = f"Moonton: empty.{parts[1] if len(parts) > 1 else ''}"
    
    # HAPUS TITIK GANDA - jika ada "empty.." ganti jadi "empty."
    text = re.sub(r'empty\.\.', 'empty.', text)
    text = re.sub(r'empty\.\.', 'empty.', text)  # lakukan dua kali untuk jaga-jaga
    
    # Bersihkan spasi berlebih
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
# =======================================================

async def read_number_from_photo_online_force(message):
    """OCR menggunakan ocr.space dengan peningkatan untuk memaksa hasil"""
    try:
        if not OCR_SPACE_API_KEY:
            logger.warning("⚠️ OCR_API_KEY tidak tersedia")
            return None
        
        logger.info("📸 Mendownload foto captcha untuk OCR paksa...")
        photo_path = await message.download_media()
        downloaded_photos.append(photo_path)
        
        # Baca file dan encode ke base64
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Coba dengan berbagai engine OCR
        ocr_engines = ['2', '1', '3']  # Coba berbagai engine
        
        for engine in ocr_engines:
            logger.info(f"🔍 Mencoba OCR dengan engine {engine}...")
            
            try:
                response = requests.post(
                    'https://api.ocr.space/parse/image',
                    data={
                        'base64Image': f'data:image/jpeg;base64,{image_data}',
                        'apikey': OCR_SPACE_API_KEY,
                        'language': 'eng',
                        'OCREngine': engine,
                        'scale': 'true',  # Skala gambar
                        'detectOrientation': 'true',
                        'filetype': 'JPG'
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if not result.get('IsErroredOnProcessing'):
                        text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                        
                        # Log hasil OCR mentah
                        logger.info(f"📝 Hasil OCR mentah (engine {engine}): {text}")
                        
                        # Bersihkan teks - ambil hanya angka
                        text_clean = re.sub(r'[^0-9]', '', text)
                        
                        # Cari pola 6 digit
                        match = re.search(r'(\d{6})', text_clean)
                        if match:
                            return match.group(1)
                        
                        # Jika tidak ada 6 digit, coba ambil 6 digit pertama
                        if len(text_clean) >= 6:
                            return text_clean[:6]
                            
            except Exception as e:
                logger.error(f"❌ OCR engine {engine} error: {e}")
                continue
        
        # Jika semua engine gagal, coba preprocessing tambahan
        logger.warning("⚠️ Semua engine OCR gagal, mencoba pendekatan alternatif...")
        
        # Coba dengan parameter berbeda
        try:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                data={
                    'base64Image': f'data:image/jpeg;base64,{image_data}',
                    'apikey': OCR_SPACE_API_KEY,
                    'language': 'eng',
                    'OCREngine': '2',
                    'isOverlayRequired': 'false',
                    'detectOrientation': 'true',
                    'scale': 'true',
                    'isTable': 'false'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('IsErroredOnProcessing'):
                    text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                    logger.info(f"📝 Hasil OCR alternatif: {text}")
                    
                    # Ambil semua digit
                    digits = re.findall(r'\d', text)
                    if len(digits) >= 6:
                        return ''.join(digits[:6])
        except Exception as e:
            logger.error(f"❌ OCR alternatif error: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Fatal OCR error: {e}")
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

def format_final_output(original_text, nickname, region, uid, sid, android, ios):
    """Format output final dengan penanganan Moonton empty yang benar"""
    
    keywords = ['Moonton', 'VK', 'Google Play', 'Tiktok', 'Facebook', 'Apple', 'GCID', 'Telegram', 'WhatsApp']
    
    # Kelompokkan baris berdasarkan keyword utama (diawali ✧)
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
            
            # Ambil nama keyword (sebelum ':')
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
                # Cari sub-baris yang diawali '-'
                sub_lines = [l for l in lines_group if l.startswith('-')]
                
                if sub_lines:
                    # Ada beberapa akun Moonton, tampilkan masing-masing
                    for sub in sub_lines:
                        sub_clean = sub.lstrip('-').strip()
                        if ':' in sub_clean:
                            label, value = sub_clean.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            # Bersihkan value
                            value = clean_bind_text(value)
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• {sub_clean}")
                else:
                    # Hanya satu baris Moonton
                    main_line = lines_group[0]
                    # Hapus '✧' dan bersihkan
                    if main_line.startswith('✧'):
                        main_line = main_line[1:].strip()
                    
                    # Cek apakah ini baris empty
                    if 'empty' in main_line.lower():
                        # Format dengan benar - pastikan tidak double dot
                        if ':' in main_line:
                            parts = main_line.split(':', 1)
                            label = parts[0].strip()
                            # Pastikan label hanya "Moonton" sekali
                            if label.count('Moonton') > 1:
                                label = 'Moonton'
                            # Gunakan "empty." tanpa tambahan titik
                            bind_info.append(f"• {label}: empty.")
                        else:
                            bind_info.append(f"• Moonton: empty.")
                    else:
                        # Tidak empty, proses normal
                        main_line = clean_bind_text(main_line)
                        
                        # Pastikan formatnya "Moonton: value"
                        if ':' in main_line:
                            label, value = main_line.split(':', 1)
                            label = label.strip()
                            value = value.strip()
                            bind_info.append(f"• {label}: {value}")
                        else:
                            bind_info.append(f"• Moonton: {main_line}")
            else:
                # Keyword lain: ambil baris utama saja
                main_line = lines_group[0]
                if main_line.startswith('✧'):
                    main_line = main_line[1:].strip()
                
                main_line = clean_bind_text(main_line)
                
                # Pastikan formatnya "Keyword: value"
                if ':' in main_line:
                    label, value = main_line.split(':', 1)
                    label = label.strip()
                    value = value.strip()
                    bind_info.append(f"• {label}: {value}")
                else:
                    bind_info.append(f"• {kw}: {main_line}")
        else:
            # Keyword tidak ditemukan
            bind_info.append(f"• {kw}: empty.")
    
    final = f"""INFORMATION ACCOUNT:
ID: {uid}
Server: {sid}
Nickname: {nickname}
Region: {region}

BIND INFO:
{chr(10).join(bind_info)}

Device Login: Android {android} | iOS {ios}"""
    
    reply_markup = {
        'inline_keyboard': [
            [{'text': 'STOK ADMIN', 'url': STOK_ADMIN_URL}]
        ]
    }
    return final, reply_markup

# ==================== FUNGSI KOMUNIKASI DENGAN BOT B (dengan logging, tanpa parse_mode) ====================
async def send_status_to_user(chat_id, text, reply_markup=None):
    """Kirim pesan status ke user melalui Bot B (pesan baru)"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        # parse_mode dihapus (None) untuk menghindari error karakter khusus
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        logger.info(f"📤 Mengirim status ke user {chat_id}: {text[:50]}...")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            msg_id = response.json()['result']['message_id']
            logger.info(f"✅ Status terkirim, message_id: {msg_id}")
            return msg_id
        else:
            logger.error(f"❌ Gagal kirim status: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Exception kirim status: {e}")
    return None

async def edit_status_message(chat_id, message_id, text, reply_markup=None):
    """Edit pesan yang sudah dikirim ke user melalui Bot B"""
    url = f"https://api.telegram.org/bot{BOT_B_TOKEN}/editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        # parse_mode dihapus (None)
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        logger.info(f"✏️ Mengedit pesan {message_id} untuk user {chat_id}")
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Pesan {message_id} berhasil diedit")
        else:
            logger.error(f"❌ Gagal edit pesan {message_id}: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Exception saat edit pesan: {e}")

# ==================== TIMEOUT CHECKER ====================
async def timeout_checker():
    """Loop untuk memonitor request yang melebihi batas waktu, 
       namun ditangguhkan selama captcha berlangsung."""
    while True:
        # Jika sedang dalam captcha, timeout ditangguhkan
        if bot_status['in_captcha']:
            await asyncio.sleep(1)
            continue

        now = time.time()
        to_remove = []
        for req_id, req_data in list(active_requests.items()):
            if now - req_data['start_time'] > REQUEST_TIMEOUT:
                logger.warning(f"⏰ Timeout untuk request {req_id}")
                await edit_status_message(
                    req_data['chat_id'],
                    req_data['message_id'],
                    "Request timeout. Silakan coba lagi."
                )
                # Hapus dari Redis
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                    logger.info(f"🗑️ Request {req_id} dihapus dari Redis karena timeout")
                except Exception as e:
                    logger.error(f"❌ Gagal hapus Redis saat timeout: {e}")
                # Hapus dari waiting flag
                waiting_for_result.pop(req_data['chat_id'], None)
                to_remove.append(req_id)
        for req_id in to_remove:
            active_requests.pop(req_id, None)
            logger.info(f"🗑️ Request {req_id} dihapus dari active_requests karena timeout")
        await asyncio.sleep(1)

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

    # ========== 1. HASIL INFO (format dengan garis) ==========
    if text.startswith('──────────────────────') and 'BIND ACCOUNT INFO' in text:
        logger.info("✅ Mendapatkan hasil info dari Bot A")
        
        # Cek apakah ada request aktif
        if not active_requests:
            logger.warning("❌ Tidak ada request aktif, hasil diabaikan")
            return

        # Ambil request yang sedang aktif (hanya satu)
        req_id, req_info = next(iter(active_requests.items()))
        user_id = req_info['chat_id']
        message_id = req_info['message_id']
        logger.info(f"📋 Request aktif ditemukan: {req_id} untuk user {user_id} dengan message_id {message_id}")

        # Ekstrak data
        id_match = re.search(r'ID:?\s*(\d+)', text)
        server_match = re.search(r'Server:?\s*(\d+)', text)
        android_match = re.search(r'Android:?\s*(\d+)', text)
        ios_match = re.search(r'iOS:?\s*(\d+)', text)

        uid = id_match.group(1) if id_match else 'Unknown'
        sid = server_match.group(1) if server_match else 'Unknown'
        android = android_match.group(1) if android_match else '0'
        ios = ios_match.group(1) if ios_match else '0'

        # Validasi via GoPay
        gopay = validate_mlbb_gopay_sync(uid, sid)
        if gopay['status']:
            nickname = gopay['username']
            region = gopay['region']
        else:
            nickname = 'Tidak diketahui'
            region = '🌍 Tidak diketahui'

        # Format output
        output, markup = format_final_output(text, nickname, region, uid, sid, android, ios)

        # Edit pesan status dengan hasil
        await edit_status_message(user_id, message_id, output, markup)

        # Bersihkan data dari memori
        try:
            del active_requests[req_id]
            waiting_for_result.pop(user_id, None)
            logger.info(f"✅ Request {req_id} dihapus dari active_requests")
        except Exception as e:
            logger.error(f"❌ Gagal hapus active_requests: {e}")

        # Hapus dari Redis
        try:
            head = r.lindex('pending_requests', 0)
            if head and head.decode('utf-8') == req_id:
                r.lpop('pending_requests')
            r.delete(req_id)
            logger.info(f"✅ Request {req_id} dihapus dari Redis")
        except Exception as e:
            logger.error(f"❌ Gagal hapus Redis: {e}")

        cleanup_downloaded_photos()
        return

    # ========== 2. VERIFIKASI SUKSES ==========
    if 'verification successful' in text.lower() or '✅ Verifikasi berhasil!' in text:
        logger.info("✅ Verifikasi sukses, auto-retry dalam 5 detik")

        # Matikan timer captcha jika ada
        if captcha_timer_task:
            captcha_timer_task.cancel()
            captcha_timer_task = None
        bot_status['in_captcha'] = False

        # Auto-retry untuk request yang sedang aktif
        if active_requests:
            await asyncio.sleep(5)
            req_id, req_info = next(iter(active_requests.items()))
            cmd = f"{req_info['command']} {req_info['args'][0]} {req_info['args'][1]}"
            await client.send_message(BOT_A_USERNAME, cmd)
            logger.info(f"🔄 Auto-retry: {cmd}")
            # Update waktu mulai
            req_info['start_time'] = time.time()
        else:
            logger.warning("⚠️ Tidak ada request aktif untuk auto-retry")
        return

   # ========== 3. CAPTCHA DENGAN FORCE VERIFY ==========
# Deteksi captcha yang lebih agresif
is_captcha = (
    message.photo or 
    'captcha' in text.lower() or 
    'kode' in text.lower() or
    'verifikasi' in text.lower() or
    re.search(r'\b\d{6}\b', text) or 
    '🔒 Masukkan kode captcha' in text or
    'masukkan kode' in text.lower()
)

if is_captcha:
    logger.warning("🚫 CAPTCHA terdeteksi! Memproses dengan force verify...")
    bot_status['in_captcha'] = True
    
    # Reset timeout untuk request yang sedang aktif (beri waktu lebih)
    if active_requests:
        for req_id, req_info in active_requests.items():
            req_info['start_time'] = time.time() + 60
            logger.info(f"⏱️ Reset timeout untuk request {req_id} karena captcha (+60 detik)")
    else:
        logger.warning("⚠️ Captcha terdeteksi tapi tidak ada request aktif")
    
    # Batalkan timer sebelumnya jika ada
    if captcha_timer_task:
        captcha_timer_task.cancel()
    
    # Set timer lebih panjang untuk captcha
    async def reset_captcha():
        await asyncio.sleep(CAPTCHA_TIMEOUT + 30)
        bot_status['in_captcha'] = False
        logger.info("Captcha timeout, status direset")
    captcha_timer_task = asyncio.create_task(reset_captcha())
    
    # AMBIL KODE CAPTCHA
    captcha_code = None
    
    # CEK DARI TEKS DULU
    all_digits = re.findall(r'\d', text)
    if len(all_digits) >= 6:
        captcha_code = ''.join(all_digits[:6])
        logger.info(f"🔑 Kode captcha dari teks: {captcha_code}")
    
    # KALAU ADA FOTO, LAKUKAN OCR BERULANG
    if not captcha_code and message.photo:
        for attempt in range(3):
            try:
                logger.info(f"📸 Percobaan OCR ke-{attempt+1} dari 3")
                captcha_code = await read_number_from_photo_online_force(message)
                
                if captcha_code and len(captcha_code) == 6:
                    logger.info(f"🔑 Kode captcha dari OCR (percobaan {attempt+1}): {captcha_code}")
                    break
                elif captcha_code:
                    logger.warning(f"OCR percobaan {attempt+1} hasil: {captcha_code} (bukan 6 digit)")
                    captcha_code = None
                else:
                    logger.warning(f"OCR percobaan {attempt+1} gagal")
                    
            except Exception as e:
                logger.error(f"❌ OCR percobaan {attempt+1} error: {e}")
            
            if attempt < 2 and not captcha_code:
                await asyncio.sleep(3)
    
    # FORCE VERIFY
    if captcha_code:
        verify_msg = f"/verify {captcha_code}"
        await client.send_message(BOT_A_USERNAME, verify_msg)
        logger.info(f"📤 Perintah verify DIPAKSA dikirim: {verify_msg}")
        
        await asyncio.sleep(3)
        if bot_status['in_captcha']:
            logger.warning("⚠️ Verify mungkin gagal, kirim ulang...")
            await client.send_message(BOT_A_USERNAME, verify_msg)
            logger.info(f"📤 Perintah verify ULANG: {verify_msg}")
    
    else:
        logger.error("❌ Gagal dapat kode captcha, coba pakai 000000")
        
        if active_requests:
            await client.send_message(BOT_A_USERNAME, "/verify 000000")
            logger.info("📤 Mencoba dengan kode dummy: 000000")
            
            await asyncio.sleep(5)
            
            if bot_status['in_captcha']:
                logger.error("❌ Masih captcha, batalkan request...")
                
                req_id, req_info = next(iter(active_requests.items()))
                await edit_status_message(
                    req_info['chat_id'],
                    req_info['message_id'],
                    "Gagal memproses captcha. Coba lagi."
                )
                
                try:
                    head = r.lindex('pending_requests', 0)
                    if head and head.decode('utf-8') == req_id:
                        r.lpop('pending_requests')
                    r.delete(req_id)
                except Exception as e:
                    logger.error(f"❌ Gagal hapus Redis: {e}")
                
                waiting_for_result.pop(req_info['chat_id'], None)
                if req_id in active_requests:
                    del active_requests[req_id]
                
                bot_status['in_captcha'] = False
                if captcha_timer_task:
                    captcha_timer_task.cancel()
                    captcha_timer_task = None
        
        cleanup_downloaded_photos()
    
    return  # PENTING: return biar ga lanjut ke handler lain

# ==================== PROSES ANTRIAN ====================
async def process_queue():
    logger.info("🔄 Queue processor started")
    while True:
        try:
            if not bot_status['in_captcha']:
                req_bytes = r.lindex('pending_requests', 0)
                if req_bytes:
                    req_id = req_bytes.decode('utf-8')
                    now = time.time()

                    # Rate limit: jangan kirim terlalu cepat
                    if req_id in sent_requests and now - sent_requests[req_id] < 15:
                        await asyncio.sleep(2)
                        continue

                    req_json = r.get(req_id)
                    if not req_json:
                        logger.warning(f"⚠️ Request {req_id} tidak ditemukan di Redis, dihapus dari antrian")
                        r.lpop('pending_requests')
                        continue

                    req_data = json.loads(req_json)
                    user_id = req_data['chat_id']
                    logger.info(f"📋 Memproses request {req_id} dari user {user_id}")

                    # Jika user ini sedang menunggu hasil (misal dari request sebelumnya), tunda
                    if waiting_for_result.get(user_id, False):
                        logger.info(f"⏳ User {user_id} masih menunggu, pindahkan ke belakang")
                        r.lpop('pending_requests')
                        r.rpush('pending_requests', req_id)
                        await asyncio.sleep(5)
                        continue

                    # Kirim status "Sedang diproses" ke user
                    status_text = "Proses request..."
                    msg_id = await send_status_to_user(user_id, status_text)
                    if not msg_id:
                        logger.error(f"❌ Gagal mengirim status ke user {user_id}, request dibatalkan")
                        r.lpop('pending_requests')
                        r.delete(req_id)
                        continue

                    # Simpan ke active_requests
                    active_requests[req_id] = {
                        'chat_id': user_id,
                        'message_id': msg_id,
                        'start_time': now,
                        'command': req_data['command'],
                        'args': req_data['args']
                    }
                    logger.info(f"✅ Request {req_id} disimpan ke active_requests dengan message_id {msg_id}")

                    # Kirim perintah ke Bot A
                    cmd = f"{req_data['command']} {req_data['args'][0]} {req_data['args'][1]}"
                    await client.send_message(BOT_A_USERNAME, cmd)
                    logger.info(f"📤 Mengirim ke Bot A: {cmd}")

                    sent_requests[req_id] = now
                    waiting_for_result[user_id] = True
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error di process_queue: {e}")
        await asyncio.sleep(2)

# ==================== MAIN ====================
async def main():
    logger.info("🚀 Memulai userbot...")

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

        # Jalankan timeout checker
        asyncio.create_task(timeout_checker())

        # Jalankan pemrosesan antrian
        await process_queue()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
