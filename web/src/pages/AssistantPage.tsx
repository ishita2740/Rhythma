import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { clearAssistantConversation, sendChatMessage, type ChatMessage } from '../api/endpoints';
import {
  clearHistory,
  loadHistory,
  saveHistory,
  type StoredMessage,
} from '../lib/chatHistory';
import { toAssistantLanguage } from '../lib/language';
import { useDocumentMeta } from '../lib/useDocumentMeta';

type UiMessage = StoredMessage;

function formatMessage(content: string): ReactNode {
  // Render the small markdown subset the Flutter app supports: **bold**
  // and lines starting with "- " or "* " as bullets.
  const lines = content.split('\n');
  return lines.map((line, i) => {
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      const text = line.trim().slice(2);
      return (
        <div key={i} className="msg-bullet">
          • {renderBold(text)}
        </div>
      );
    }
    return <div key={i}>{renderBold(line) || '\u00A0'}</div>;
  });
}

function renderBold(text: string): ReactNode {
  const parts = text.split('**');
  return parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}

function friendlyError(error: unknown, t: (k: string) => string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      response?: { status?: number; data?: { detail?: string } };
    };
    if (axiosErr.response?.status === 429) return t('assistant.rateLimited');
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail;
  }
  return t('assistant.errorPrefix');
}

export function AssistantPage() {
  useDocumentMeta('meta.assistant.title', 'meta.assistant.description');
  const { t, i18n } = useTranslation();
  const { user } = useAuth();

  const userId = user?.id;

  const greeting = useCallback(
    (): UiMessage => ({
      role: 'model',
      content: t('assistant.welcome', { name: user?.username ?? 'User' }),
    }),
    [t, user?.username],
  );

  // Seeded from *this account's* transcript. The initializer runs once,
  // before the id is necessarily known, so the effect below re-seeds when
  // it arrives — and, crucially, when it changes: mounting with A's
  // messages and then having B sign in is the exact sequence that used to
  // show one user another's conversation.
  const [messages, setMessages] = useState<UiMessage[]>(() => {
    const saved = loadHistory(userId);
    return saved.length > 0 ? saved : [greeting()];
  });
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = loadHistory(userId);
    setMessages(saved.length > 0 ? saved : [greeting()]);
    // `greeting` is intentionally out of the dependency list: it changes
    // whenever the language does, and re-seeding the transcript on a
    // language switch would discard the conversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, typing]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || typing) return;

    const next: UiMessage[] = [...messages, { role: 'user', content: trimmed }];
    setMessages(next);
    setInput('');
    setTyping(true);

    const history: ChatMessage[] = next
      .filter((m) => !m.isError)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      // `i18n.language` is a UI tag — it can be `en-US` from the browser
      // detector, or `bn`, which the web app supports and the assistant
      // does not. The backend validates this field now, so it has to be
      // a code the assistant actually serves.
      const result = await sendChatMessage(
        trimmed,
        toAssistantLanguage(i18n.language),
        history,
      );
      const withReply: UiMessage[] = [...next, { role: 'model', content: result.response }];
      setMessages(withReply);
      saveHistory(userId, withReply);
    } catch (error) {
      const withError: UiMessage[] = [
        ...next,
        { role: 'model', content: `${t('assistant.errorPrefix')}: ${friendlyError(error, t)}`, isError: true },
      ];
      setMessages(withError);
      saveHistory(userId, withError);
    } finally {
      setTyping(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };

  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState('');

  /**
   * Clear the conversation — both copies of it.
   *
   * This used to be two lines: drop one `localStorage` key, reset the
   * screen. The transcript the model is actually given lives on the
   * server, and `POST /assistant/chat` loads it into the prompt on every
   * turn — so a user who cleared a conversation about a possible
   * pregnancy asked something unrelated next and got an answer composed
   * in the context of the one she had just deleted (issue #509).
   *
   * The order matters. The server copy goes first, and the local copy and
   * the screen are only cleared once it is gone: emptying the screen
   * first and then failing would leave the user believing something that
   * is not true, which is the exact failure being fixed. A failure is
   * reported and nothing is cleared.
   */
  const clearConversation = async () => {
    if (clearing) return;

    setClearing(true);
    setClearError('');

    try {
      await clearAssistantConversation();
    } catch {
      setClearError(t('assistant.clearFailed'));
      return;
    } finally {
      setClearing(false);
    }

    clearHistory(userId);
    setMessages([greeting()]);
  };

  const showSuggestions = messages.filter((m) => !m.isError).length <= 1;
  // Only offered once there is something to clear — a button that does
  // nothing is worse than no button.
  const canClear = messages.some((m) => m.role === 'user');

  return (
    <div className="assistant-page page">
      <header className="page-header assistant-header">
        <div>
          <h1>{t('assistant.title')}</h1>
          <p className="card-sub">{t('assistant.subtitle')}</p>
        </div>
        <select
          className="language-select"
          value={i18n.language.slice(0, 2)}
          onChange={(e) => void i18n.changeLanguage(e.target.value)}
          aria-label="Select AI Assistant Language"
        >
          <option value="en">English (EN)</option>
          <option value="hi">Hindi (हिन्दी)</option>
          <option value="mr">Marathi (मराठी)</option>
          <option value="ta">Tamil (தமிழ்)</option>
          <option value="te">Telugu (తెలుగు)</option>
          <option value="kn">Kannada (ಕನ್ನಡ)</option>
          <option value="ml">Malayalam (മലയാളം)</option>
          <option value="gu">Gujarati (ગુજરાતી)</option>
          <option value="bn">Bengali (বাংলা)</option>
        </select>
      </header>

      <div className="chat-list" ref={listRef}>
        {showSuggestions ? (
          <div className="suggestions">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                className="chip"
                onClick={() => void send(t(`assistant.suggest${n}`))}
              >
                {t(`assistant.suggest${n}`)}
              </button>
            ))}
          </div>
        ) : null}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble ${msg.role}${msg.isError ? ' is-error' : ''}`}>
            {msg.role === 'model' && !msg.isError ? <span className="bubble-avatar">💗</span> : null}
            <div className="bubble-body">{formatMessage(msg.content)}</div>
          </div>
        ))}

        {typing ? (
          <div className="chat-bubble model">
            <span className="bubble-avatar">💗</span>
            <div className="typing-indicator">
              <span />
              <span />
              <span />
            </div>
          </div>
        ) : null}
      </div>

      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('assistant.inputPlaceholder')}
          aria-label={t('assistant.inputPlaceholder')}
        />
        <button type="submit" className="send-btn" disabled={typing || !input.trim()}>
          {t('assistant.send')}
        </button>
      </form>

      {/* Said out loud, because it was not obvious and it is the kind of
          thing someone on a shared computer needs to know before she
          types a question about her body (#420). */}
      <div className="assistant-privacy">
        {/* This used to read "kept on this device and cleared when you log
            out", which was not true — the conversation is also stored
            against the account and is what the assistant is given on every
            turn (#509). Saying where data lives is only worth doing if the
            sentence is accurate. */}
        <p className="disclaimer">{t('assistant.conversationStorage')}</p>
        {canClear ? (
          <button
            type="button"
            className="ghost-btn"
            onClick={() => void clearConversation()}
            disabled={clearing}
          >
            {clearing ? t('assistant.clearing') : t('assistant.clearConversation')}
          </button>
        ) : null}
        {clearError ? (
          <p className="error-text" role="alert">
            {clearError}
          </p>
        ) : null}
      </div>

      <p className="disclaimer">{t('assistant.disclaimer')}</p>
    </div>
  );
}
