import { useCallback, useEffect, useRef, useState } from 'react';
import { postNdjson } from './ndjson.js';
import { sendMessage } from './agentClient.js';

let nextId = 0;
const uid = () => `m${++nextId}`;
const newThread = () => crypto.randomUUID();

// Conversation state. Agent messages accumulate their ReAct steps while the
// loop runs, then stream the final answer. `threadId` is the backend memory key:
// same id = the agent remembers; reset() starts a fresh conversation.
// onUi(event): screen commands from the agent. getUiState(): what the user sees now.
//
// Approvals: when the agent wants to delete files the loop pauses and an
// { type: 'approval' } event arrives; the message gets an `approval` card and the
// chat waits until decide(true|false) resumes the agent (POST /api/chat/approval).
export function useChat({ onUi, getUiState } = {}) {
  const [messages, setMessages] = useState([]);
  const hooksRef = useRef({ onUi, getUiState });
  hooksRef.current = { onUi, getUiState };
  const [busy, setBusy] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(null); // agent message id
  const abortRef = useRef(null);
  const threadRef = useRef(newThread());

  useEffect(() => () => abortRef.current?.abort(), []);

  const patchAgent = (id, fn) => setMessages((list) => list.map((m) => (m.id === id ? fn(m) : m)));

  // Same handler for a new turn and for a resumed one: events land on `agentId`.
  const run = useCallback(async (agentId, request) => {
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const handle = (event) => {
      if (event.type === 'answer') {
        patchAgent(agentId, (m) => ({ ...m, status: 'answering', text: m.text + event.text }));
      } else if (event.type === 'done') {
        patchAgent(agentId, (m) => ({ ...m, status: m.status === 'error' ? 'error' : event.awaiting_approval ? 'waiting' : 'done' }));
        if (event.awaiting_approval) setPendingApproval(agentId);
      } else if (event.type === 'ui') {
        hooksRef.current.onUi?.(event);
      } else if (event.type === 'approval') {
        patchAgent(agentId, (m) => ({ ...m, approval: { ...event, status: 'pending' } }));
      } else if (event.type === 'error') {
        patchAgent(agentId, (m) => ({ ...m, status: 'error', error: event.text }));
      } else {
        // Resumed turns re-send the paused tool call: skip steps we already have.
        patchAgent(agentId, (m) =>
          event.id && m.steps.some((s) => s.id === event.id && s.type === event.type)
            ? m
            : { ...m, steps: [...m.steps, { type: event.type, text: event.text, id: event.id }] }
        );
      }
    };
    try {
      await request(handle, controller.signal);
    } catch (err) {
      if (err.name !== 'AbortError') patchAgent(agentId, (m) => ({ ...m, status: 'error', error: err.message }));
    } finally {
      setBusy(false);
    }
  }, []);

  const send = useCallback(
    async (raw) => {
      const text = raw.trim();
      if (!text || busy || pendingApproval) return;
      const agentId = uid();
      setMessages((list) => [
        ...list,
        { id: uid(), role: 'user', text },
        { id: agentId, role: 'agent', steps: [], text: '', status: 'thinking' },
      ]);
      await run(agentId, (onEvent, signal) =>
        sendMessage(text, threadRef.current, onEvent, { signal, uiState: hooksRef.current.getUiState?.() })
      );
    },
    [busy, pendingApproval, run]
  );

  // The user's answer to the approval card.
  const decide = useCallback(
    async (approve) => {
      const agentId = pendingApproval;
      if (!agentId || busy) return;
      setPendingApproval(null);
      patchAgent(agentId, (m) => ({
        ...m,
        status: 'thinking',
        text: m.text ? `${m.text.trimEnd()}\n\n` : '',
        approval: { ...m.approval, status: approve ? 'approved' : 'rejected' },
      }));
      await run(agentId, (onEvent, signal) =>
        postNdjson('/api/chat/approval', { thread_id: threadRef.current, approve }, onEvent, { signal })
      );
    },
    [pendingApproval, busy, run]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    threadRef.current = newThread();
    setMessages([]);
    setPendingApproval(null);
    setBusy(false);
  }, []);

  return { messages, busy, send, reset, decide, awaitingApproval: !!pendingApproval };
}
