const { TelegramClient } = require('gramjs');
const { StringSession } = require('gramjs/sessions');
const redis = require('redis');
const dotenv = require('dotenv');
const axios = require('axios');
const sharp = require('sharp');
const Tesseract = require('tesseract.js');

dotenv.config();

// Inisialisasi Redis
const redisClient = redis.createClient({
  url: process.env.REDIS_URL
});

// Session dari environment
const sessionString = process.env.SESSION_STRING;
const client = new TelegramClient(
  new StringSession(sessionString),
  Number(process.env.API_ID),
  process.env.API_HASH,
  { connectionRetries: 5 }
);

const BOT_A_USERNAME = process.env.BOT_A_USERNAME;
const BOT_A_ID = process.env.BOT_A_CHAT_ID;

let botStatus = {
  inCaptcha: false,
  lastCaptchaTime: 0
};

// Helper: Kirim notifikasi ke admin
async function notifyAdmin(message) {
  if (process.env.ADMIN_CHAT_ID && process.env.ADMIN_CHAT_ID !== '0') {
    try {
      await axios.post(
        `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
        {
          chat_id: process.env.ADMIN_CHAT_ID,
          text: `🤖 Relay Bot:\n${message}`
        }
      );
    } catch (err) {
      console.error('Gagal notifikasi admin:', err.message);
    }
  }
}

// Helper: Solve captcha dengan OCR
async function solveCaptcha(photo) {
  try {
    // Download foto
    const buffer = await photo.downloadMedia({});
    
    // Proses dengan sharp untuk OCR
    const processed = await sharp(buffer)
      .grayscale()
      .threshold(200)
      .toBuffer();

    // OCR dengan Tesseract
    const { data: { text } } = await Tesseract.recognize(
      processed,
      'eng',
      {
        logger: m => console.log('OCR:', m.status),
        tessedit_char_whitelist: '0123456789'
      }
    );

    // Ambil 6 digit pertama
    const digits = text.match(/\d{6}/);
    
    if (digits) {
      console.log(`✅ OCR berhasil: ${digits[0]}`);
      return digits[0];
    } else {
      console.log(`❌ OCR gagal: ${text}`);
      return null;
    }
  } catch (err) {
    console.error('Error OCR:', err);
    return null;
  }
}

// Main function
async function start() {
  await redisClient.connect();
  console.log('✅ Redis connected');

  await client.start();
  console.log('✅ Userbot started!');

  // Kirim /start ke Bot A
  try {
    await client.sendMessage(BOT_A_USERNAME, { message: '/start' });
    console.log('✅ Session dengan Bot A aktif');
  } catch (err) {
    console.log('⚠️ Gagal kirim /start:', err.message);
  }

  // Handler untuk pesan baru
  client.addEventHandler(async (update) => {
    if (update.className === 'UpdateNewMessage') {
      const message = update.message;
      
      // Hanya pesan dari Bot A
      if (message.peerId?.userId?.value === BOT_A_ID) {
        const text = message.message || '';
        
        // CEK CAPTCHA (foto + kata kunci)
        if (message.media && (text.includes('captcha') || text.includes('verify'))) {
          console.log('🚫 CAPTCHA DETECTED!');
          
          botStatus.inCaptcha = true;
          botStatus.lastCaptchaTime = Date.now();
          
          await notifyAdmin('Captcha detected, solving...');
          
          // Solve captcha
          const code = await solveCaptcha(message.media);
          
          if (code) {
            // Kirim verifikasi
            await client.sendMessage(BOT_A_USERNAME, { message: `/verify ${code}` });
            console.log(`✅ Verifikasi dikirim: /verify ${code}`);
            
            await new Promise(r => setTimeout(r, 3000));
            botStatus.inCaptcha = false;
            
            await notifyAdmin('Captcha solved!');
            
            // Proses ulang request pending
            await retryPendingRequests();
          } else {
            console.log('❌ Gagal solve captcha');
            await notifyAdmin('OCR failed, waiting 5 minutes...');
            await new Promise(r => setTimeout(r, 300000));
            botStatus.inCaptcha = false;
          }
          
          return;
        }
        
        // RESPON NORMAL (hasil /info)
        if (!botStatus.inCaptcha && !message.media) {
          const requestId = await redisClient.lPop('pending_requests');
          
          if (requestId) {
            const requestData = JSON.parse(await redisClient.get(requestId));
            
            // Forward ke user via Bot B
            try {
              await axios.post(
                `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
                {
                  chat_id: requestData.chatId,
                  text: message.message,
                  parse_mode: 'HTML'
                }
              );
              console.log(`✅ Response ke user ${requestData.chatId}`);
            } catch (err) {
              console.error('Gagal forward:', err.message);
              await redisClient.rPush('pending_requests', requestId);
            }
          }
        }
      }
    }
  });

  // Queue processor
  async function processQueue() {
    while (true) {
      if (!botStatus.inCaptcha) {
        const requestId = await redisClient.lPop('pending_requests');
        
        if (requestId) {
          const requestData = JSON.parse(await redisClient.get(requestId));
          
          // Kirim ke Bot A
          const cmd = `${requestData.command} ${requestData.args.join(' ')}`;
          await client.sendMessage(BOT_A_USERNAME, { message: cmd });
          console.log(`📤 Request: ${cmd}`);
          
          // Simpan kembali untuk nanti diambil responsenya
          await redisClient.setEx(requestId, 300, JSON.stringify(requestData));
        }
      }
      
      await new Promise(r => setTimeout(r, 3000)); // Jeda 3 detik
    }
  }

  async function retryPendingRequests() {
    while (true) {
      const requestId = await redisClient.lPop('pending_requests');
      if (!requestId) break;
      
      const requestData = JSON.parse(await redisClient.get(requestId));
      const cmd = `${requestData.command} ${requestData.args.join(' ')}`;
      
      await client.sendMessage(BOT_A_USERNAME, { message: cmd });
      console.log(`🔄 Retry: ${cmd}`);
      
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  // Jalankan queue processor
  processQueue();
}

start().catch(console.error);

// Graceful shutdown
process.on('SIGINT', () => {
  client.disconnect();
  redisClient.quit();
  process.exit();
});
