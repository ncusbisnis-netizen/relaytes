const { TelegramClient } = require("telegram");
const { StringSession } = require("telegram/sessions");
const { Connection } = require("telegram/network/connection");
const redis = require('redis');
const axios = require('axios');

// Redis connection
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || process.env.REDISCLOUD_URL
});

redisClient.on('error', (err) => console.log('Redis Client Error', err));
redisClient.connect().then(() => console.log('✅ Redis connected'));

// Telegram client dengan WebSocket
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessionString = process.env.SESSION_STRING || '';

console.log('🚀 Starting userbot...');
console.log('Session length:', sessionString.length);

// PAKAI WEB SOCKET CONNECTION
const client = new TelegramClient(
  new StringSession(sessionString),
  apiId,
  apiHash,
  {
    connectionRetries: 5,
    useWSS: true,  // WebSocket Secure
    baseDc: 4,
    requestTimeout: 60000,
    floodSleepThreshold: 90,
    deviceModel: 'Heroku',
    systemVersion: 'Linux',
    appVersion: '1.0.0',
    langCode: 'en',
    timeout: 30000,
    // Tambahkan parameter untuk WebSocket
    connection: new Connection('wss://dc4-1.telegram.org:443', {
      useWSS: true,
      proxy: null,
      timeout: 30000
    })
  }
);

client.setLogLevel('none');

let botStatus = {
  inCaptcha: false
};

async function start() {
  try {
    console.log('🔄 Mencoba koneksi WebSocket...');
    
    await client.connect();
    console.log('✅ Client terhubung');
    
    await client.start();
    console.log('✅ Userbot started!');

    // Test koneksi
    try {
      const me = await client.getMe();
      console.log('✅ Login sebagai:', me.username || me.firstName);
    } catch (err) {
      console.log('⚠️ Gagal getMe:', err.message);
    }

    // Test ke Bot A
    try {
      await client.sendMessage('bengkelmlbb_bot', { message: '/start' });
      console.log('✅ Connected to @bengkelmlbb_bot');
    } catch (err) {
      console.log('⚠️ Gagal kirim /start:', err.message);
    }

    // Event handler
    client.addEventHandler(async (update) => {
      try {
        if (update.className === 'UpdateNewMessage' || update.className === 'UpdateNewChannelMessage') {
          const message = update.message;
          
          // Cek dari Bot A
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
              setTimeout(() => { botStatus.inCaptcha = false; }, 60000);
              return;
            }

            // Forward ke user
            if (!botStatus.inCaptcha && !message.media) {
              const requestId = await redisClient.lPop('pending_requests');
              if (requestId) {
                const requestData = JSON.parse(await redisClient.get(requestId));
                await axios.post(
                  `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
                  { chat_id: requestData.chatId, text: text }
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
    console.error('❌ Failed to start:', err);
    process.exit(1);
  }
}

start();
