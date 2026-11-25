// getFile / download failed (Telegram bots can only fetch files up to 20 MB, or a network error).
const u = $('Parse update').first().json;
return [send(u.chat_id, '❌ Could not download the file from Telegram. Bots can receive files up to 20 MB: '
  + 'send a smaller PDF or photo.', { reply_to_message_id: u.message_id })];
