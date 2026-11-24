// Show "typing…" while the agent works (answers take a few seconds).
const u = $('Parse update').first().json;
return [{ json: { method: 'sendChatAction', payload: { chat_id: u.chat_id, action: 'typing' } } }];
