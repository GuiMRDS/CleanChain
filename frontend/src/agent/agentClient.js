// Chat with the LangChain ReAct agent (POST /api/chat). The backend streams:
//   { type: 'action' | 'observation', text, ... }
//   { type: 'answer', text }   — answer tokens, in order
//   { type: 'ui', command, args } — agent asks the screen to change (e.g. focus_folder)
//   { type: 'error', text }
//   { type: 'done' }
import { postNdjson } from './ndjson.js';

export async function sendMessage(text, threadId, onEvent, { signal, uiState } = {}) {
  let finished = false;
  await postNdjson(
    '/api/chat',
    { message: text, thread_id: threadId, ui_state: uiState ?? null },
    (event) => {
      if (event.type === 'done') finished = true;
      onEvent(event);
    },
    { signal }
  );
  if (!finished) onEvent({ type: 'done' });
}
