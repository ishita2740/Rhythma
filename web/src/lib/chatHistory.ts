/**
 * The assistant transcript on this device, kept to the account that wrote it.
 *
 * `AssistantPage` stored the conversation under one fixed key:
 *
 *     const HISTORY_KEY = 'rhythma_chat_history';
 *
 * Nothing in that key identifies the account. `localStorage` is scoped to
 * the origin, not to the session, and nothing ever removed the entry — so
 * on a shared device, which is the ordinary case for the people this app
 * is built for:
 *
 * 1. A signs in and asks the assistant about her bleeding, her pain, a
 *    possible pregnancy. Every turn is written to that key.
 * 2. A signs out. `logout()` clears the React state and the cookies. It
 *    does not touch `localStorage`.
 * 3. B signs in on the same browser, opens the assistant, and is looking
 *    at A's conversation — rendered as her own, because the messages
 *    carry no owner.
 *
 * B could also continue that thread: the next request posts A's turns as
 * `history`, so A's disclosures become context for B's question.
 *
 * Three rules follow, and they are all enforced here rather than in the
 * page, so a second screen that wants the transcript cannot get them
 * wrong:
 *
 * **The key names the account.** A transcript is only ever read back for
 * the user it was written for. There is no path that renders one user's
 * messages to another, because there is no key that would resolve.
 *
 * **Signing out clears it.** Not "eventually", and not only from the
 * screen the user happened to be on.
 *
 * **What is retained is bounded.** Every exchange rewrote the whole
 * array, and only the last ten turns are ever *sent*, so the rest was
 * being stored for nothing.
 *
 * Related but distinct: #123 is the Flutter app's on-device storage. This
 * is the web app, and the specific failure is that the data crossed
 * accounts.
 */

/** One turn as the screen holds it. `isError` turns are never sent back. */
export interface StoredMessage {
  role: 'user' | 'model';
  content: string;
  isError?: boolean;
}

const KEY_PREFIX = 'rhythma_chat_history';

/**
 * The single unnamespaced key every account used to share.
 *
 * Still referenced so it can be *deleted*. A user who upgrades has an
 * entry sitting in her browser from before this change, and it is not
 * hers to keep any more than it was the next person's to read.
 */
export const LEGACY_KEY = KEY_PREFIX;

/**
 * How many turns to keep on the device.
 *
 * The request only ever carries the last ten, so anything past that is
 * stored without being used. Twenty leaves the screen with visible
 * scrollback while keeping the stored blob small — this is a browser on a
 * shared machine, and the smallest useful footprint is the right one.
 */
export const MAX_STORED_MESSAGES = 20;

function keyFor(userId: string): string {
  return `${KEY_PREFIX}:${userId}`;
}

function storage(): Storage | null {
  // Absent in a non-browser environment, and throwing in a browser with
  // storage disabled or a full quota. A transcript that cannot be cached
  // is a degraded experience, never a broken screen.
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

/**
 * Remove the shared key written before transcripts were namespaced.
 *
 * Called on load and on logout. Deliberately unconditional: there is no
 * way to tell whose conversation it holds, which is the entire problem
 * with it, so the only safe thing to do with it is drop it.
 */
export function clearLegacyHistory(): void {
  try {
    storage()?.removeItem(LEGACY_KEY);
  } catch {
    // Nothing to do and nothing worth reporting.
  }
}

/**
 * This account's stored transcript, or an empty list.
 *
 * Returns nothing for a missing `userId` rather than falling back to a
 * shared key — "we don't know who is asking" must never resolve to
 * somebody's conversation.
 */
export function loadHistory(userId: string | undefined | null): StoredMessage[] {
  clearLegacyHistory();

  if (!userId) return [];

  const store = storage();
  if (!store) return [];

  try {
    const raw = store.getItem(keyFor(userId));
    if (!raw) return [];

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter((entry): entry is StoredMessage => {
        if (!entry || typeof entry !== 'object') return false;
        const message = entry as Partial<StoredMessage>;
        return (
          typeof message.content === 'string' &&
          message.content.length > 0 &&
          (message.role === 'user' || message.role === 'model')
        );
      })
      .slice(-MAX_STORED_MESSAGES);
  } catch {
    // Corrupt JSON, or storage that refused to read. An empty transcript
    // is a worse experience than a restored one and a much better one
    // than a blank screen.
    return [];
  }
}

/** Write this account's transcript, keeping only the recent tail. */
export function saveHistory(
  userId: string | undefined | null,
  messages: StoredMessage[],
): void {
  if (!userId) return;

  try {
    storage()?.setItem(
      keyFor(userId),
      JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)),
    );
  } catch {
    // A full quota must not take the conversation down with it.
  }
}

/** Drop one account's transcript. */
export function clearHistory(userId: string | undefined | null): void {
  try {
    if (userId) storage()?.removeItem(keyFor(userId));
  } catch {
    // See above.
  }
}

/**
 * Drop every transcript on this device, whoever wrote it.
 *
 * What logout and account deletion call. Scoped to this app's own keys by
 * the prefix, so nothing else in `localStorage` is touched.
 *
 * Clearing *all* of them rather than just the departing user's is
 * deliberate. Signing out on a shared computer is the moment the next
 * person sits down, and leaving a third account's conversation behind
 * because it was not the one being signed out of would reproduce the bug
 * one step removed.
 */
export function clearAllHistories(): void {
  const store = storage();
  if (!store) return;

  try {
    const doomed: string[] = [];
    for (let index = 0; index < store.length; index++) {
      const key = store.key(index);
      if (key && key.startsWith(KEY_PREFIX)) doomed.push(key);
    }
    // Collected first, then removed: removing during iteration shifts the
    // indices underneath the loop and skips every other key.
    for (const key of doomed) store.removeItem(key);
  } catch {
    // See above.
  }
}
