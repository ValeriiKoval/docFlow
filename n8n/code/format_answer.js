// After POST /ask: send the agent's answer as plain text (Claude is asked for plain text, so no HTML escaping issues).
const u = $('Parse update').first().json;
const r = $input.first().json;
const text = r.statusCode === 200
  ? String(r.body.answer || '').slice(0, 4000) || 'No answer found.'
  : `❌ Could not get an answer (${r.statusCode || 'error'}).`;
return [{ json: { method: 'sendMessage', payload: { chat_id: u.chat_id, text, reply_to_message_id: u.message_id } } }];
