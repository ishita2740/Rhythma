import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  LEGACY_KEY,
  MAX_STORED_MESSAGES,
  clearAllHistories,
  clearHistory,
  clearLegacyHistory,
  loadHistory,
  saveHistory,
  type StoredMessage,
} from './chatHistory';

// The single case this module exists for is the first one below: two
// accounts on one browser must not see each other's conversation. On a
// shared family laptop or a phone passed around — which is the ordinary
// case for the people this app is built for — the previous fixed key
// meant the next person to sign in was shown the last person's questions
// about her body.

const ASHA = 'user-asha';
const BEGUM = 'user-begum';

function message(content: string, role: StoredMessage['role'] = 'user'): StoredMessage {
  return { role, content };
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('one browser, two accounts', () => {
  it('does not show one account another account’s conversation', () => {
    saveHistory(ASHA, [message('is this much bleeding normal?')]);

    expect(loadHistory(BEGUM)).toEqual([]);
  });

  it('gives each account back its own transcript', () => {
    saveHistory(ASHA, [message('asha question')]);
    saveHistory(BEGUM, [message('begum question')]);

    expect(loadHistory(ASHA)[0].content).toBe('asha question');
    expect(loadHistory(BEGUM)[0].content).toBe('begum question');
  });

  it('returns nothing when there is no id to read for', () => {
    // "We don't know who is asking" must never resolve to somebody's
    // conversation.
    saveHistory(ASHA, [message('private')]);

    expect(loadHistory(undefined)).toEqual([]);
    expect(loadHistory(null)).toEqual([]);
    expect(loadHistory('')).toEqual([]);
  });

  it('writes nothing when there is no id to write for', () => {
    saveHistory(undefined, [message('orphan')]);

    expect(localStorage.length).toBe(0);
  });
});

describe('the shared key written before this change', () => {
  it('is deleted on load', () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify([message('someone else’s')]));

    loadHistory(ASHA);

    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it('is never rendered to whoever happens to be signed in', () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify([message('someone else’s')]));

    expect(loadHistory(ASHA)).toEqual([]);
  });

  it('is dropped even with nobody signed in', () => {
    // There is no way to tell whose conversation it holds, which is the
    // whole problem with it.
    localStorage.setItem(LEGACY_KEY, JSON.stringify([message('unattributable')]));

    clearLegacyHistory();

    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });
});

describe('clearing', () => {
  it('drops one account’s transcript', () => {
    saveHistory(ASHA, [message('gone')]);

    clearHistory(ASHA);

    expect(loadHistory(ASHA)).toEqual([]);
  });

  it('drops every transcript on the device', () => {
    // What logout calls. Leaving a third account's conversation behind
    // because it was not the one being signed out of would reproduce the
    // bug one step removed.
    saveHistory(ASHA, [message('a')]);
    saveHistory(BEGUM, [message('b')]);

    clearAllHistories();

    expect(loadHistory(ASHA)).toEqual([]);
    expect(loadHistory(BEGUM)).toEqual([]);
  });

  it('leaves other applications’ storage alone', () => {
    localStorage.setItem('some_other_app', 'keep me');
    saveHistory(ASHA, [message('a')]);

    clearAllHistories();

    expect(localStorage.getItem('some_other_app')).toBe('keep me');
  });

  it('removes every key even though removal shifts the indices', () => {
    // Removing during iteration skips every other key, which would leave
    // half the transcripts behind.
    for (const id of ['u1', 'u2', 'u3', 'u4', 'u5']) {
      saveHistory(id, [message(id)]);
    }

    clearAllHistories();

    expect(localStorage.length).toBe(0);
  });
});

describe('what is kept', () => {
  it('bounds the stored transcript', () => {
    // Only the last ten turns are ever sent, so the rest was being stored
    // for nothing — on a shared browser, indefinitely.
    const many = Array.from({ length: 60 }, (_, i) => message(`turn ${i}`));

    saveHistory(ASHA, many);

    const loaded = loadHistory(ASHA);
    expect(loaded).toHaveLength(MAX_STORED_MESSAGES);
    expect(loaded.at(-1)?.content).toBe('turn 59');
  });

  it('keeps the most recent turns, not the first ones', () => {
    saveHistory(
      ASHA,
      Array.from({ length: MAX_STORED_MESSAGES + 5 }, (_, i) => message(`t${i}`)),
    );

    expect(loadHistory(ASHA)[0].content).toBe('t5');
  });

  it('drops entries that are not messages', () => {
    localStorage.setItem(
      `${LEGACY_KEY}:${ASHA}`,
      JSON.stringify([
        message('real'),
        null,
        { role: 'system', content: 'not a role we render' },
        { role: 'user' },
        { role: 'user', content: '' },
      ]),
    );

    expect(loadHistory(ASHA)).toEqual([message('real')]);
  });

  it('survives corrupt JSON', () => {
    localStorage.setItem(`${LEGACY_KEY}:${ASHA}`, '{not json');

    expect(loadHistory(ASHA)).toEqual([]);
  });

  it('survives a payload that is not an array', () => {
    localStorage.setItem(`${LEGACY_KEY}:${ASHA}`, JSON.stringify({ role: 'user' }));

    expect(loadHistory(ASHA)).toEqual([]);
  });
});

describe('storage that refuses to cooperate', () => {
  it('does not throw when the quota is full', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });

    // A transcript that cannot be cached is a degraded experience. A
    // conversation that throws mid-send is a broken screen.
    expect(() => saveHistory(ASHA, [message('a')])).not.toThrow();
  });

  it('does not throw when reading fails', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });

    expect(loadHistory(ASHA)).toEqual([]);
  });
});
