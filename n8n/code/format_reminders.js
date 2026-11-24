// GET /deadlines?days_left=7,3,1,0 -> one reminder message per Telegram chat the documents came from.
// Documents uploaded by other channels (API, email) have no chat and are skipped here.
const days = (n) => (n === 0 ? 'today' : n === 1 ? 'tomorrow' : `in ${n} days`);
const byChat = new Map();
for (const { json: d } of $input.all()) {
  if (d.source !== 'telegram' || !d.source_ref) continue;
  const chat = d.source_ref.split(':')[0];
  if (!byChat.has(chat)) byChat.set(chat, []);
  byChat.get(chat).push(d);
}
const out = [];
for (const [chat_id, items] of byChat) {
  const lines = items.map((d) => {
    const what = d.kind === 'payment_due'
      ? `💳 Pay ${money(d.total_amount, d.currency) || ''} by ${d.date}`
      : `📅 Expires ${d.date}`;
    const who = [TYPE[d.doc_type] || d.doc_type, d.counterparty, d.document_number && `№ ${d.document_number}`]
      .filter(Boolean).map(esc).join(', ');
    const unchecked = d.status === 'needs_review' ? ' ⚠️ <i>not reviewed</i>' : '';
    return `${esc(what)} (<b>${days(d.days_left)}</b>)\n    ${who} · #${d.document_id}${unchecked}`;
  });
  out.push(send(Number(chat_id), `⏰ <b>Deadline reminders</b>\n\n${lines.join('\n\n')}`));
}
return out;
