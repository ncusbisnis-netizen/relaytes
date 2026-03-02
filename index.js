// File untuk menjalankan kedua proses
const { fork } = require('child_process');
const path = require('path');

console.log('🚀 Starting relay system...');

// Jalankan Bot B
const botB = fork(path.join(__dirname, 'bot-b.js'));
console.log('✅ Bot B process started (PID: ' + botB.pid + ')');

// Jalankan Userbot Relay
const relay = fork(path.join(__dirname, 'userbot-relay.js'));
console.log('✅ Userbot relay started (PID: ' + relay.pid + ')');

// Handle exit
process.on('SIGINT', () => {
  console.log('Shutting down...');
  botB.kill();
  relay.kill();
  process.exit();
});

process.on('SIGTERM', () => {
  console.log('Shutting down...');
  botB.kill();
  relay.kill();
  process.exit();
});
