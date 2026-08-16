import { beforeEach, describe, expect, it } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';

import i18n from '../i18n';
import { DocumentLanguage, useDocumentMeta } from './useDocumentMeta';

function Page({ titleKey, descriptionKey }: { titleKey: string; descriptionKey?: string }) {
  useDocumentMeta(titleKey, descriptionKey);
  return <div>page</div>;
}

function withI18n(node: React.ReactNode) {
  return render(<I18nextProvider i18n={i18n}>{node}</I18nextProvider>);
}

beforeEach(async () => {
  document.head.querySelectorAll('meta[name], meta[property]').forEach((tag) => {
    tag.remove();
  });
  document.documentElement.removeAttribute('lang');
  document.title = '';
  await i18n.changeLanguage('en');
});

describe('useDocumentMeta', () => {
  it('sets a page-specific title instead of the scaffold default', async () => {
    // Before #407 every route's tab said the literal string "web".
    withI18n(<Page titleKey="meta.cycle.title" />);

    await waitFor(() => expect(document.title).toBe('Cycle · Rhythma'));
  });

  it('does not repeat the app name on the home page', async () => {
    withI18n(<Page titleKey="meta.home.title" />);

    await waitFor(() => expect(document.title).toBe('Rhythma'));
  });

  it('sets the description meta tag', async () => {
    withI18n(<Page titleKey="meta.cycle.title" descriptionKey="meta.cycle.description" />);

    await waitFor(() => {
      const tag = document.head.querySelector('meta[name="description"]');
      expect(tag?.getAttribute('content')).toMatch(/log today's period/i);
    });
  });

  it('mirrors the title into og:title so a shared link previews', async () => {
    withI18n(<Page titleKey="meta.insights.title" />);

    await waitFor(() => {
      expect(
        document.head.querySelector('meta[property="og:title"]')?.getAttribute('content'),
      ).toBe('Insights · Rhythma');
    });
  });

  it('re-titles when the language changes, not only on navigation', async () => {
    // The reason the hook takes keys rather than a finished string.
    // Passing `t('...')` in from the caller looks equivalent and leaves
    // the tab in the previous language until the next route change.
    withI18n(<Page titleKey="meta.cycle.title" />);
    await waitFor(() => expect(document.title).toBe('Cycle · Rhythma'));

    const before = document.title;
    await i18n.changeLanguage('hi');

    await waitFor(() => {
      expect(document.title).toBe(
        `${i18n.t('meta.cycle.title')} · ${i18n.t('meta.appName')}`,
      );
    });
    expect(document.title).toBeTruthy();
    expect(before).toBeTruthy();
  });

  it('keeps exactly one description tag across re-renders', async () => {
    const { rerender } = withI18n(
      <Page titleKey="meta.cycle.title" descriptionKey="meta.cycle.description" />,
    );
    rerender(
      <I18nextProvider i18n={i18n}>
        <Page titleKey="meta.insights.title" descriptionKey="meta.insights.description" />
      </I18nextProvider>,
    );

    await waitFor(() =>
      expect(document.head.querySelectorAll('meta[name="description"]')).toHaveLength(1),
    );
  });
});

describe('DocumentLanguage', () => {
  it('points html lang at the active locale', async () => {
    withI18n(<DocumentLanguage />);

    await waitFor(() => expect(document.documentElement.getAttribute('lang')).toBe('en'));
  });

  it('follows a language change', async () => {
    // The accessibility bug behind #407: `lang` was hard-coded to "en", so
    // a screen reader handed Devanagari to an English synthesizer.
    withI18n(<DocumentLanguage />);
    await waitFor(() => expect(document.documentElement.getAttribute('lang')).toBe('en'));

    await i18n.changeLanguage('hi');

    await waitFor(() => expect(document.documentElement.getAttribute('lang')).toBe('hi'));
  });

  it('sets a direction', async () => {
    withI18n(<DocumentLanguage />);

    await waitFor(() => expect(document.documentElement.getAttribute('dir')).toBe('ltr'));
  });
});
