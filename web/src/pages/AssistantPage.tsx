import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { sendChatMessage, type ChatMessage } from '../api/endpoints';
import {
  clearHistory,
  loadHistory,
  saveHistory,
  type StoredMessage,
} from '../lib/chatHistory';
import { isAssistantLanguageFallback, toAssistantLanguage } from '../lib/language';
import { APP_LANGUAGES, baseLanguage } from '../lib/supportedLanguages';
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

  const clearConversation = () => {
    clearHistory(userId);
    setMessages([greeting()]);
  };

  // True when the assistant cannot answer in the language the interface
  // is currently in, so the screen can say so before she types rather
  // than after she reads an English reply.
  const assistantFallsBack = isAssistantLanguageFallback(i18n.language);

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
        {/* Built from `APP_LANGUAGES`, not from a literal. The literal
            listed nine options including Bengali, which is a complete
            locale here and not a language `POST /assistant/chat` serves —
            so choosing it switched the whole interface to Bengali and
            then answered in English with no explanation (#512).

            `.slice(0, 2)` was wrong for `mai`, `sat` and `sd` as well: it
            truncated a three-letter code to two and matched no option, so
            the select fell back to showing the first one. */}
        <select
          className="language-select"
          value={baseLanguage(i18n.language)}
          onChange={(e) => void i18n.changeLanguage(e.target.value)}
          aria-label={t('assistant.languageLabel')}
        >
          {APP_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code} lang={lang.code}>
              {lang.nativeName}
            </option>
          ))}
        </select>
      </header>

      {/* `isAssistantLanguageFallback` was written for exactly this, with
          a docstring explaining why the silent fallback "looks like the
          app ignoring the language setting" — and then nothing ever
          imported it. Nine of the seventeen shipped locales hit this
          path, and every one of them was silent (#512). */}
      {assistantFallsBack ? (
        <p className="disclaimer assistant-language-notice" role="status">
          {t('assistant.languageFallback', {
            language: t('assistant.englishLanguageName'),
          })}
        </p>
      ) : null}

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
        <p className="disclaimer">{t('assistant.storedOnDevice')}</p>
        {canClear ? (
          <button type="button" className="ghost-btn" onClick={clearConversation}>
            {t('assistant.clearConversation')}
          </button>
        ) : null}
      </div>

      <p className="disclaimer">{t('assistant.disclaimer')}</p>
    </div>
  );
}
