// After POST /documents/{id}/review: confirm in the chat and remove the buttons from the reviewed message.
const u = $('Parse update').first().json;
const r = $input.first().json;
const out = [];
const ok = r.statusCode === 200;

if (u.callback_id) {
  out.push(answer(u.callback_id, ok ? 'Saved' : 'Error'));
  if (ok) {
    out.push({ json: { method: 'editMessageReplyMarkup',
      payload: { chat_id: u.chat_id, message_id: u.message_id, reply_markup: { inline_keyboard: [] } } } });
  }
}
if (!ok) {
  out.push(send(u.chat_id, `❌ Document #${u.doc_id}: ${apiError(r)}`));
  return out;
}
const d = r.body;
const by = d.reviewed_by ? ` (${esc(d.reviewed_by)})` : '';
const text = {
  approved: `✅ Document #${d.id} approved${by}.`,
  rejected: `🗑 Document #${d.id} rejected${by}.`,
  corrected: `✏️ Document #${d.id} corrected${by}.\n\n${summary(d)}`,
}[d.status] || `Document #${d.id}: ${esc(d.status)}`;
const warn = d.status === 'corrected' && d.issues?.length
  ? `\n\n⚠️ Please note:\n${d.issues.map((i) => `• ${esc(i)}`).join('\n')}` : '';
out.push(send(u.chat_id, text + warn));
return out;
