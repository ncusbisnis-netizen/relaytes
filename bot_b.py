from flask import Flask, request, jsonify
import redis
import os
import time
import json
import logging

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Config dari environment
BOT_TOKEN = os.environ.get('BOT_B_TOKEN', '')
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('REDISCLOUD_URL', ''))

# Validasi environment
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN tidak ditemukan!")
    exit(1)

if not REDIS_URL:
    logger.error("❌ REDIS_URL tidak ditemukan!")
    exit(1)

# Redis connection
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    exit(1)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logger.info(f"📩 Webhook received: {json.dumps(data)[:200]}")
        
        # Ambil data pesan
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            telegram_user_id = message['from']['id']
            text = message.get('text', '')
            
            # SIMPAN CHAT ID KE REDIS (BUAT RELAY)
            chat_id_key = f"user_chat:{telegram_user_id}"
            r.setex(chat_id_key, 86400, chat_id)  # Simpan 24 jam
            logger.info(f"💾 Saved chat_id {chat_id} for telegram user {telegram_user_id}")
            
            # CEK PERINTAH /info
            if text.startswith('/info'):
                parts = text.split()
                if len(parts) == 3:
                    _, mlbb_id, server_id = parts
                    
                    # Validasi angka
                    if mlbb_id.isdigit() and server_id.isdigit():
                        # Buat request ID
                        request_id = f"req:{telegram_user_id}:{int(time.time())}"
                        
                        # FORMAT BOT B (SIMPLE)
                        request_data = {
                            'telegram_user_id': telegram_user_id,
                            'mlbb_id': mlbb_id,
                            'server_id': server_id,
                            'chat_id': chat_id,
                            'command': '/info'
                        }
                        
                        # Simpan ke Redis
                        r.setex(request_id, 300, json.dumps(request_data))
                        r.rpush('pending_requests', request_id)
                        
                        logger.info(f"📤 Request queued: {request_id} untuk user {telegram_user_id}")
            
            # CEK PERINTAH /cek
            elif text.startswith('/cek'):
                parts = text.split()
                if len(parts) == 3:
                    _, mlbb_id, server_id = parts
                    
                    if mlbb_id.isdigit() and server_id.isdigit():
                        request_id = f"req:{telegram_user_id}:{int(time.time())}"
                        
                        request_data = {
                            'telegram_user_id': telegram_user_id,
                            'mlbb_id': mlbb_id,
                            'server_id': server_id,
                            'chat_id': chat_id,
                            'command': '/cek'
                        }
                        
                        r.setex(request_id, 300, json.dumps(request_data))
                        r.rpush('pending_requests', request_id)
                        
                        logger.info(f"📤 Request queued: {request_id} untuk user {telegram_user_id}")
            
            # CEK PERINTAH /find
            elif text.startswith('/find'):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    _, query = parts
                    
                    request_id = f"req:{telegram_user_id}:{int(time.time())}"
                    
                    request_data = {
                        'telegram_user_id': telegram_user_id,
                        'query': query,
                        'chat_id': chat_id,
                        'command': '/find'
                    }
                    
                    r.setex(request_id, 300, json.dumps(request_data))
                    r.rpush('pending_requests', request_id)
                    
                    logger.info(f"📤 Request queued: {request_id} untuk user {telegram_user_id}")
        
        # GAK USAH NGASIH RESPON KE USER!
        # LANGSUNG RETURN 200 AJA
        return jsonify({'ok': True})
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'time': time.time(),
        'redis': 'connected'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Bot B starting on port {port} (NO RESPONSE MODE)")
    app.run(host='0.0.0.0', port=port)
