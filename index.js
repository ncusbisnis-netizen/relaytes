// File untuk menjalankan kedua proses
const { fork } = require('child_process');
const path = require('path');

console.log('🚀 Starting relay system...');

// Jalankan Bot B
const botB = fork(path.join(__dirname, 'bot-b.js'));
console.log('✅ Bot B process started');

// Jalankan Userbot Relay
const relay = fork(path.join(__dirname, 'userbot-relay.js'));
console.log('✅ Userbot relay started');

// Handle exit
process.on('SIGINT', () => {
  botB.kill();
  relay.kill();
  process.exit();
});
