import test from 'node:test';
import assert from 'node:assert/strict';

import { readStoredThread, writeStoredThread, clearStoredThread } from './chat-storage.js';

test('chat storage round-trips the most recent thread and unread state', () => {
  const key = 'wealth-copilot-thread';
  clearStoredThread(key);

  const thread = {
    conversation_id: 'conv-123',
    target: { type: 'dashboard', title: 'Ask Wealth Copilot' },
    messages: [
      { role: 'user', text: 'What matters today?' },
      { role: 'assistant', text: 'The market is quiet.' },
    ],
    unread_count: 1,
    updated_at: '2026-08-18T00:00:00Z',
  };

  writeStoredThread(key, thread);
  assert.deepEqual(readStoredThread(key), thread);
  clearStoredThread(key);
  assert.equal(readStoredThread(key), null);
});
