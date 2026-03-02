const { TelegramClient } = require("telegram");
const { StringSession } = require("telegram/sessions");
const redis = require('redis');
const axios = require('axios');
const { MTProto } = require('@mtproto/core');

// Redis connection
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || process.env.REDISCLOUD_URL
});

redisClient.on('error', (err) => console.log('Redis Client Error', err));
redisClient.connect().then(() => console.log('✅ Redis connected'));

// Telegram client dengan konfigurasi yang benar
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessionString = process.env.SESSION_STRING || '';

console.log('🚀 Starting userbot...');
console.log('Session length:', sessionString.length);

const client = new TelegramClient(
  new StringSession(sessionString),
  apiId,
  apiHash,
  {
    connectionRetries: 5,
    useWSS: true,
    baseDc: 2,
    requestTimeout: 30000,
    floodSleepThreshold: 60
  }
);

let botStatus = {
  inCaptcha: false
};

async function start() {
  try {
    await client.start();
    console.log('✅ Userbot started!');

    // Test koneksi ke Bot A
    try {
      await client.sendMessage('bengkelmlbb_bot', { message: '/start' });
      console.log('✅ Connected to @bengkelmlbb_bot');
    } catch (err) {
      console.log('⚠️ Could not send /start:', err.message);
    }

    // Event handler
    client.addEventHandler(async (update) => {
      try {
        if (update.className === 'UpdateNewMessage' || update.className === 'UpdateNewChannelMessage') {
          const message = update.message;
          
          // Cek apakah dari Bot A
          let isFromBotA = false;
          if (message.peerId && message.peerId.className === 'PeerUser') {
            if (message.peerId.userId && message.peerId.userId.value.toString() === process.env.BOT_A_CHAT_ID) {
              isFromBotA = true;
            }
          }

          if (isFromBotA) {
            const text = message.message || '';
            console.log('📩 From Bot A:', text.substring(0, 50));

            // Cek captcha
            if (message.media && (text.includes('captcha') || text.includes('verify'))) {
              console.log('🚫 CAPTCHA DETECTED!');
              botStatus.inCaptcha = true;
              
              // Proses captcha (sederhana dulu)
              setTimeout(() => {
                botStatus.inCaptcha = false;
              }, 60000); // Anggap 1 menit
              
              return;
            }

            // Forward ke user
            if (!botStatus.inCaptcha && !message.media) {
              const requestId = await redisClient.lPop('pending_requests');
              if (requestId) {
                const requestData = JSON.parse(await redisClient.get(requestId));
                
                await axios.post(
                  `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
                  {
                    chat_id: requestData.chatId,
                    text: text
                  }
                );
                console.log(`✅ Forwarded to user ${requestData.chatId}`);
              }
            }
          }
        }
      } catch (err) {
        console.error('Event handler error:', err);
      }
    });

    // Queue processor
    setInterval(async () => {
      if (!botStatus.inCaptcha) {
        const requestId = await redisClient.lPop('pending_requests');
        if (requestId) {
          const requestData = JSON.parse(await redisClient.get(requestId));
          const cmd = `${requestData.command} ${requestData.args.join(' ')}`;
          
          try {
            await client.sendMessage('bengkelmlbb_bot', { message: cmd });
            console.log('📤 Request:', cmd);
            await redisClient.setEx(requestId, 300, JSON.stringify(requestData));
          } catch (err) {
            console.error('Send error:', err.message);
            await redisClient.rPush('pending_requests', requestId);
          }
        }
      }
    }, 3000);

  } catch (err) {
    console.error('Failed to start:', err);
    process.exit(1);
  }
}

start();
