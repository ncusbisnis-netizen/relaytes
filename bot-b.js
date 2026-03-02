const { Telegraf } = require('telegraf');
const redis = require('redis');
const dotenv = require('dotenv');

dotenv.config();

// Inisialisasi Bot B
const bot = new Telegraf(process.env.BOT_B_TOKEN);

// Redis client
const redisClient = redis.createClient({
  url: process.env.REDIS_URL
});

redisClient.on('error', (err) => console.error('Redis Error:', err));

async function start() {
  await redisClient.connect();
  console.log('✅ Redis connected');

  // Command /start
  bot.start((ctx) => {
    ctx.reply(
      '🤖 *Relay Bot untuk @bengkelmlbb_bot*\n\n' +
      'Gunakan perintah:\n' +
      '/info [user_id] [zone_id]\n' +
      'Contoh: /info 643461181 8554',
      { parse_mode: 'Markdown' }
    );
  });

  // Command /info
  bot.command('info', async (ctx) => {
    const userId = ctx.from.id;
    const chatId = ctx.chat.id;
    const args = ctx.message.text.split(' ').slice(1);

    if (args.length < 2) {
      return ctx.reply(
        '❌ Format salah!\n' +
        'Gunakan: /info [user_id] [zone_id]'
      );
    }

    const requestId = `req:${userId}:${chatId}:${Date.now()}`;
    
    const requestData = {
      userId,
      chatId,
      command: '/info',
      args,
      status: 'pending',
      time: Date.now()
    };

    // Simpan ke Redis
    await redisClient.setEx(requestId, 300, JSON.stringify(requestData));
    await redisClient.rPush('pending_requests', requestId);

    ctx.reply(
      `⏳ *Memproses request...*\n` +
      `User ID: \`${args[0]}\`\n` +
      `Zone ID: \`${args[1]}\`\n\n` +
      `Tunggu sebentar...`,
      { parse_mode: 'Markdown' }
    );

    console.log(`📤 Request dari ${userId}: /info ${args.join(' ')}`);
  });

  // Health check
  bot.command('ping', (ctx) => ctx.reply('pong'));

  bot.launch();
  console.log('✅ Bot B started!');
}

start();

// Graceful shutdown
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
