// ✏️ pressed: ask the reviewer to reply with "field=value" lines (force_reply keeps the thread).
const u = $('Parse update').first().json;
const text = [
  `✏️ Correcting document #${u.doc_id}.`,
  'Reply to this message with <code>field=value</code> lines, for example:',
  '<code>total_amount=1516.40</code>',
  '<code>due_date=2026-03-19</code>',
  '',
  'Fields: doc_type, counterparty, recipient, document_number, issue_date, currency, total_amount, due_date, valid_from, valid_until. An empty value or null clears the field.',
].join('\n');
return [answer(u.callback_id, 'Waiting for the correction'), send(u.chat_id, text, { reply_markup: { force_reply: true } })];
