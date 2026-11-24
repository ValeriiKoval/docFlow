// Classify a Telegram update into one route for the Switch node.
// kinds: file | review | fix_prompt | correction | help | ignore
const body = $input.first().json.body || {};
const msg = body.message;
const cq = body.callback_query;
const out = { kind: 'ignore', update_id: body.update_id };

const who = (u) => (u && (u.username || [u.first_name, u.last_name].filter(Boolean).join(' ') || String(u.id))) || null;

if (cq) {
  const [action, id] = String(cq.data || '').split(':');
  Object.assign(out, {
    chat_id: cq.message.chat.id,
    message_id: cq.message.message_id,
    callback_id: cq.id,
    doc_id: Number(id),
    action,
    reviewer: who(cq.from),
  });
  if (action === 'fix') out.kind = 'fix_prompt';
  else if (action === 'approve' || action === 'reject') out.kind = 'review';
} else if (msg) {
  Object.assign(out, { chat_id: msg.chat.id, message_id: msg.message_id, reviewer: who(msg.from) });
  const replied = msg.reply_to_message && msg.reply_to_message.text;
  const ref = replied && replied.match(/#(\d+)/);
  if (msg.document) {
    Object.assign(out, { kind: 'file', file_id: msg.document.file_id, file_name: msg.document.file_name || null });
  } else if (msg.photo && msg.photo.length) {
    // Telegram sends several sizes; the last one is the largest
    Object.assign(out, { kind: 'file', file_id: msg.photo[msg.photo.length - 1].file_id, file_name: null });
  } else if (ref && (msg.text || '').includes('=')) {
    // reply to "✏️ Correcting document #12" with lines "field=value"
    const fields = {};
    for (const line of msg.text.split('\n')) {
      const m = line.match(/^\s*([a-z_]+)\s*=\s*(.*?)\s*$/);
      if (m) fields[m[1]] = m[2] === '' || m[2].toLowerCase() === 'null' ? null : m[2];
    }
    Object.assign(out, { kind: 'correction', doc_id: Number(ref[1]), action: 'correct', fields });
  } else {
    out.kind = 'help';
  }
}
return [{ json: out }];
