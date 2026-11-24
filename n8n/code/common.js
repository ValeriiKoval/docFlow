// Shared helpers, prepended to the Code nodes that format Telegram messages.
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const TYPE = {
  invoice: 'Invoice', contract: 'Contract', insurance: 'Insurance policy',
  receipt: 'Receipt', utility_bill: 'Utility bill', other: 'Other document',
};
const money = (v, cur) => (v == null ? null : `${Number(v).toFixed(2)} ${cur || ''}`.trim());

function summary(d) {
  const f = d.fields || {};
  const rows = [
    ['Type', TYPE[f.doc_type] || f.doc_type],
    ['From', f.counterparty],
    ['To', f.recipient],
    ['Number', f.document_number],
    ['Date', f.issue_date],
    ['Amount', money(f.total_amount, f.currency)],
    ['Pay by', f.due_date],
    ['Valid', f.valid_from || f.valid_until ? `${f.valid_from || '?'} — ${f.valid_until || '?'}` : null],
  ];
  return rows.filter(([, v]) => v != null && v !== '').map(([k, v]) => `${k}: <b>${esc(v)}</b>`).join('\n');
}

const send = (chat_id, text, extra = {}) => ({ json: { method: 'sendMessage', payload: { chat_id, text, parse_mode: 'HTML', ...extra } } });
const answer = (callback_query_id, text) => ({ json: { method: 'answerCallbackQuery', payload: { callback_query_id, text } } });
const reviewKeyboard = (id, canApprove = true) => ({
  inline_keyboard: [[
    ...(canApprove ? [{ text: '✅ Approve', callback_data: `approve:${id}` }] : []),
    { text: '✏️ Correct', callback_data: `fix:${id}` },
    { text: '🗑 Reject', callback_data: `reject:${id}` },
  ]],
});
const apiError = (r) => {
  const detail = r.body && typeof r.body === 'object' ? r.body.detail ?? JSON.stringify(r.body) : r.body;
  return `${r.statusCode || r.error?.message || 'error'}: ${esc(typeof detail === 'string' ? detail : JSON.stringify(detail))}`;
};
