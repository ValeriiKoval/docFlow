// Any other message (/start, text): short instructions.
const u = $('Parse update').first().json;
const text = [
  '👋 <b>DocFlow AI</b>: incoming document intake.',
  '',
  'Send a PDF or a photo of an invoice, contract, insurance policy, receipt or utility bill.',
  'I will recognise the type, counterparty, amount, dates and number, save the document and remind you of deadlines.',
  'If I am not sure about something, I will ask you to check it with the ✅ / ✏️ / 🗑 buttons.',
].join('\n');
return [send(u.chat_id, text)];
