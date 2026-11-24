// /start, /help and anything that is not a file or a question: short instructions.
const u = $('Parse update').first().json;
const text = [
  '👋 <b>DocFlow AI</b>: incoming document intake.',
  '',
  '📎 Send a PDF or a photo of an invoice, contract, insurance policy, receipt or utility bill. I will recognise the type, counterparty, amount, dates and number and save the document.',
  'If I am not sure about something, I will ask you to check it with the ✅ / ✏️ / 🗑 buttons.',
  '',
  '💬 Ask in plain text, for example: "When does the insurance expire?" or "How much did we pay Kappa IT this year?"',
  '⏰ /deadlines: upcoming deadlines. Every morning at 9:00 I remind you of payments and of expiring policies and contracts (7, 3 and 1 day before and on the day).',
].join('\n');
return [send(u.chat_id, text)];
