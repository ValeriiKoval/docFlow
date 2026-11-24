// Chat not in TELEGRAM_ALLOWED_CHAT_IDS: tell the user their chat id so the owner can allow it.
const u = $('Parse update').first().json;
if (!u.chat_id) return [];
const out = [];
if (u.callback_id) out.push(answer(u.callback_id, 'No access'));
out.push(send(u.chat_id, `⛔ This chat has no access to DocFlow.\nChat ID: <code>${esc(u.chat_id)}</code>. Ask the administrator to add it to TELEGRAM_ALLOWED_CHAT_IDS.`));
return out;
