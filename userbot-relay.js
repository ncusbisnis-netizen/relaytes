const { TelegramClient } = require("telegram");
const { StringSession } = require("telegram/sessions");
const redis = require('redis');
const axios = require('axios');

console.log('🚀 Starting userbot...');
console.log('Node version:', process.version);

// Cek environment variables
const requiredEnv = ['API_ID', 'API_HASH', 'SESSION_STRING', 'BOT_B_TOKEN', 'BOT_A_CHAT_ID'];
requiredEnv.forEach(varName => {
  if (!process.env[varName]) {
    console.error(`❌ Missing required env: ${varName}`);
    process.exit(1);
  }
  console.log(`✅ ${varName} is set`);
});

// Redis connection
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || process.env.REDISCLOUD_URL
});

redisClient.on('error', (err) => console.log('Redis Client Error:', err.message));

// Telegram client
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessionString = process.env.SESSION_STRING;

console.log('API ID:', apiId);
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
    floodSleepThreshold: 60,
    deviceModel: 'Heroku',
    systemVersion: 'Linux',
    appVersion: '1.0.0'
  }
);

let botStatus = { inCaptcha: false };

async function start() {
  try {
    // Connect Redis
    await redisClient.connect();
    console.log('✅ Redis connected');

    // Connect Telegram
    console.log('🔄 Connecting to Telegram...');
    await client.connect();
    console.log('✅ Telegram connected');

    await client.start();
    console.log('✅ Userbot started');

    // Test connection
    const me = await client.getMe();
    console.log('✅ Logged in as:', me.username || me.firstName);

    // Test send to Bot A
    try {
      await client.sendMessage('bengkelmlbb_bot', { message: '/start' });
      console.log('✅ Message sent to @bengkelmlbb_bot');
    } catch (err) {
      console.log('⚠️ Cannot send to Bot A:', err.message);
    }

    // Event handler
    client.addEventHandler(async (update) => {
      try {
        if (update.message && update.message.peerId?.userId?.value?.toString() === process.env.BOT_A_CHAT_ID) {
          const text = update.message.message || '';
          console.log('📩 From Bot A:', text.substring(0, 50));

          if (update.message.media && text.includes('captcha')) {
            console.log('🚫 Captcha detected');
            botStatus.inCaptcha = true;
            setTimeout(() => { botStatus.inCaptcha = false; }, 60000);
            return;
          }

          const requestId = await redisClient.lPop('pending_requests');
          if (requestId) {
            const data = JSON.parse(await redisClient.get(requestId));
            await axios.post(
              `https://api.telegram.org/bot${process.env.BOT_B_TOKEN}/sendMessage`,
              { chat_id: data.chatId, text }
            );
            console.log('✅ Forwarded');
          }
        }
      } catch (err) {
        console.error('Event error:', err.message);
      }
    });

    // Queue processor
    setInterval(async () => {
      if (!botStatus.inCaptcha) {
        const requestId = await redisClient.lPop('pending_requests');
        if (requestId) {
          const data = JSON.parse(await redisClient.get(requestId));
          const cmd = `${data.command} ${data.args.join(' ')}`;
          try {
            await client.sendMessage('bengkelmlbb_bot', { message: cmd });
            console.log('📤 Sent:', cmd);
            await redisClient.setEx(requestId, 300, JSON.stringify(data));
          } catch (err) {
            console.error('Send error:', err.message);
            await redisClient.rPush('pending_requests', requestId);
          }
        }
      }
    }, 3000);

  } catch (err) {
    console.error('❌ Fatal error:', err);
    console.error('Stack:', err.stack);
    process.exit(1);
  }
}

start();
