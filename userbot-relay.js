const { TelegramClient } = require("telegram");
const { StringSession } = require("telegram/sessions");
const redis = require('redis');
const axios = require('axios');

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
console.log('Session first 50 chars:', sessionString.substring(0, 50));
console.log('API ID:', apiId);
console.log('Bot A Chat ID:', process.env.BOT_A_CHAT_ID);

const client = new TelegramClient(
  new StringSession(sessionString),
  apiId,
  apiHash,
  {
    connectionRetries: 5,
    useWSS: false,
    baseDc: 4,
    requestTimeout: 60000,
    floodSleepThreshold: 90,
    deviceModel: 'Heroku',
    systemVersion: 'Linux',
    appVersion: '1.0.0',
    langCode: 'en',
    timeout: 30000
  }
);

client.setLogLevel('debug');

let botStatus = {
  inCaptcha: false
};

async function start() {
  try {
    // Coba koneksi ke beberapa DC
    const dcs = [4, 2, 5, 1, 3];
    let connected = false;
    
    for (const dc of dcs) {
      console.log(`🔄 Mencoba DC ${dc}...`);
      console.log(`Setting DC ${dc} dengan host dc${dc}.telegram.org`);
      
      try {
        // Coba dengan hostname
        client.session.setDC(dc, `dc${dc}.telegram.org`, 443);
        console.log(`Mencoba connect ke dc${dc}.telegram.org:443`);
        
        await client.connect();
        console.log(`✅ Berhasil connect ke DC ${dc}`);
        
        await new Promise(r => setTimeout(r, 2000));
        
        // Cek apakah benar-benar connect
        const me = await client.getMe();
        console.log('✅ Login sebagai:', me.username || me.firstName);
        console.log('User ID:', me.id);
        
        connected = true;
        break;
      } catch (err) {
        console.log(`❌ DC ${dc} gagal dengan hostname`);
        console.log('Error name:', err.name);
        console.log('Error message:', err.message);
        console.log('Error code:', err.code);
        console.log('Error stack:', err.stack);
        
        // Coba dengan IP langsung sebagai fallback
        console.log(`Mencoba DC ${dc} dengan IP 149.154.167.51`);
        try {
          client.session.setDC(dc, '149.154.167.51', 443);
          await client.connect();
          console.log(`✅ Berhasil connect ke DC ${dc} dengan IP`);
          
          const me = await client.getMe();
          console.log('✅ Login sebagai:', me.username || me.firstName);
          
          connected = true;
          break;
        } catch (err2) {
          console.log(`❌ DC ${dc} gagal juga dengan IP`);
          console.log('Error name:', err2.name);
          console.log('Error message:', err2.message);
          console.log('Error code:', err2.code);
          console.log('Error stack:', err2.stack);
        }
        
        continue;
      }
    }
    
    if (!connected) {
      throw new Error('❌ Gagal konek ke semua DC');
    }
    
    console.log('✅ Client connected, memulai start...');
    await client.start();
    console.log('✅ Userbot started!');

    // Test koneksi ke Bot A
    try {
      console.log('Mencoba kirim /start ke @bengkelmlbb_bot...');
      await client.sendMessage('bengkelmlbb_bot', { message: '/start' });
      console.log('✅ Connected to @bengkelmlbb_bot');
    } catch (err) {
      console.log('⚠️ Could not send /start:', err.message);
      console.log('Error details:', err);
    }

    // Event handler
    client.addEventHandler(async (update) => {
      try {
        console.log('📨 Update received:', update.className);
        
        if (update.className === 'UpdateNewMessage' || update.className === 'UpdateNewChannelMessage') {
          const message = update.message;
          
          if (message.peerId && message.peerId.className === 'PeerUser') {
            console.log('Message from user:', message.peerId.userId?.value);
          }
          
          // Cek apakah dari Bot A
          let isFromBotA = false;
          if (message.peerId && message.peerId.className === 'PeerUser') {
            if (message.peerId.userId && message.peerId.userId.value.toString() === process.env.BOT_A_CHAT_ID) {
              isFromBotA = true;
              console.log('✅ Message dari Bot A terdeteksi');
            }
          }

          if (isFromBotA) {
            const text = message.message || '';
            console.log('📩 From Bot A:', text.substring(0, 100));

            // Cek captcha
            if (message.media && (text.includes('captcha') || text.includes('verify'))) {
              console.log('🚫 CAPTCHA DETECTED!');
              botStatus.inCaptcha = true;
              
              setTimeout(() => {
                console.log('✅ Captcha timeout selesai');
                botStatus.inCaptcha = false;
              }, 60000);
              
              return;
            }

            // Forward ke user
            if (!botStatus.inCaptcha && !message.media) {
              const requestId = await redisClient.lPop('pending_requests');
              if (requestId) {
                const requestData = JSON.parse(await redisClient.get(requestId));
                console.log('Forward ke user:', requestData.chatId);
                
                await axios.post(
                  `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
                  {
                    chat_id: requestData.chatId,
                    text: text
                  }
                );
                console.log(`✅ Forwarded to user ${requestData.chatId}`);
              } else {
                console.log('Tidak ada pending request');
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
            console.log('📤 Mengirim request ke Bot A:', cmd);
            await client.sendMessage('bengkelmlbb_bot', { message: cmd });
            console.log('✅ Request terkirim');
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
    console.error('Error name:', err.name);
    console.error('Error message:', err.message);
    console.error('Error stack:', err.stack);
    process.exit(1);
  }
}

start();
