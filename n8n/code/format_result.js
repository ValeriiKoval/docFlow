// After POST /extract: reply in the chat; documents that need review get ✅ / ✏️ / 🗑 buttons.
const u = $('Parse update').first().json;
const r = $input.first().json;
const reply = { reply_to_message_id: u.message_id };

if (r.statusCode !== 200) {
  return [send(u.chat_id, `❌ Could not process the file (${apiError(r)})`, reply)];
}
const { duplicate, document: d } = r.body;
const head = `<b>${esc(TYPE[d.fields?.doc_type] || 'Document')}</b> · #${d.id}`;

if (duplicate) {
  return [send(u.chat_id, `ℹ️ This file is already in the database: ${head}, status <i>${esc(d.status)}</i>.\n\n${summary(d)}`, reply)];
}
if (d.status === 'auto_accepted') {
  return [send(u.chat_id, `✅ ${head}\nRecognised and saved automatically (confidence ${d.confidence}).\n\n${summary(d)}`, reply)];
}
if (d.status === 'needs_review') {
  const why = (d.issues || []).map((i) => `• ${esc(i)}`).join('\n');
  return [send(u.chat_id, `⚠️ ${head}\nNeeds review:\n${why}\n\n${summary(d)}`,
    { ...reply, reply_markup: reviewKeyboard(d.id) })];
}
// failed: extraction error; allow manual entry or rejection
return [send(u.chat_id, `❌ Document #${d.id}: could not be recognised (${esc(d.error)}).\nYou can enter the fields manually.`,
  { ...reply, reply_markup: reviewKeyboard(d.id, false) })];
