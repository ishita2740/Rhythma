/**
 * The behaviour `role="dialog"` promises (issue #502).
 *
 * Every case here is about what happens to focus and to the rest of the
 * page, not about what the markup looks like — the old code had all the
 * right attributes and none of the behaviour, so asserting on attributes
 * is how this regresses without anyone noticing.
 *
 * Tab is dispatched with `userEvent.tab()`, which walks the DOM's tab
 * order rather than firing a keydown at whatever is focused. That means
 * these tests exercise the trap the way a keyboard does: `preventDefault`
 * in the handler is what stops the walk leaving the panel, and a hole in
 * it shows up here as focus landing on the button behind the overlay.
 */

import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { Modal } from './Modal';

/**
 * A page with something focusable behind the dialog.
 *
 * `behind` is the escape hatch the trap has to close: it is a real button
 * in the tab order, covered by the backdrop and nothing else.
 */
function Harness({ withForm = false }: { withForm?: boolean } = {}) {
  const [open, setOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open dialog
      </button>
      <button type="button">Behind the overlay</button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Sleep"
        panelClassName="quick-log-panel"
        onSubmit={
          withForm
            ? (event) => {
                event.preventDefault();
                setSubmitted(true);
              }
            : undefined
        }
      >
        <button type="button">First</button>
        <button type="button">Second</button>
        {withForm ? <button type="submit">Save</button> : null}
        <button type="button" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </Modal>

      {submitted ? <p>Saved</p> : null}
    </div>
  );
}

function dialog() {
  return screen.getByRole('dialog');
}

describe('opening', () => {
  it('announces itself as a modal dialog named by its visible heading', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    const panel = dialog();
    expect(panel).toHaveAttribute('aria-modal', 'true');
    // The name comes from the heading on screen, not from a second copy
    // in an aria-label that can drift away from it.
    expect(panel).toHaveAccessibleName('Sleep');
    expect(screen.getByRole('heading', { name: 'Sleep' })).toBeInTheDocument();
  });

  it('moves focus into the dialog', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    // Previously focus stayed on the tile behind the backdrop, so a
    // screen-reader user was told nothing had opened.
    expect(dialog()).toHaveFocus();
  });

  it('renders nothing at all while closed', () => {
    render(<Harness />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('the trap', () => {
  it('cycles Tab from the last control back to the first', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    await user.tab(); // panel → First
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Second' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    // The step that used to walk out into the page.
    await user.tab();
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
  });

  it('cycles Shift+Tab from the first control back to the last', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    await user.tab();
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('wraps Shift+Tab from the panel itself rather than stepping out', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    expect(dialog()).toHaveFocus();

    await user.tab({ shift: true });

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('never lands on a control behind the overlay', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    // Grabbed before opening, because once the dialog is up this button is
    // `aria-hidden` and `getByRole` — which queries the accessibility tree
    // — genuinely cannot see it any more. That is the fix working, and it
    // is why the reference has to be taken first.
    const behind = screen.getByRole('button', { name: 'Behind the overlay' });

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    for (let step = 0; step < 8; step += 1) {
      await user.tab();
      expect(behind).not.toHaveFocus();
      expect(dialog().contains(document.activeElement)).toBe(true);
    }
  });
});

describe('the rest of the page', () => {
  it('is hidden from assistive technology while the dialog is up', async () => {
    const user = userEvent.setup();
    const { baseElement } = render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    // Everything in <body> except the portal the dialog rendered into.
    const hidden = Array.from(baseElement.children).filter(
      (child) => !child.contains(dialog()),
    );
    expect(hidden.length).toBeGreaterThan(0);
    for (const element of hidden) {
      expect(element).toHaveAttribute('aria-hidden', 'true');
      // `inert` as well as `aria-hidden`: the first hides it from a
      // screen reader, the second takes it out of the keyboard order too.
      expect(element).toHaveAttribute('inert');
    }
  });

  it('is handed back when the dialog closes', async () => {
    const user = userEvent.setup();
    const { baseElement } = render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    for (const element of Array.from(baseElement.children)) {
      expect(element).not.toHaveAttribute('aria-hidden');
      expect(element).not.toHaveAttribute('inert');
    }
  });

  it('does not scroll under the overlay', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    expect(document.body.style.overflow).toBe('hidden');

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(document.body.style.overflow).not.toBe('hidden');
    });
  });
});

describe('closing', () => {
  it('closes on Escape', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes on a press that starts and ends on the backdrop', async () => {
    const user = userEvent.setup();
    const { baseElement } = render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    const backdrop = baseElement.querySelector('.modal-backdrop');
    expect(backdrop).not.toBeNull();
    await user.click(backdrop as Element);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('stays open when a press starts inside the panel and ends outside it', async () => {
    // Selecting text in a field and releasing past the edge of the panel
    // used to count as a backdrop click and throw the entry away.
    const user = userEvent.setup();
    const { baseElement } = render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    const backdrop = baseElement.querySelector('.modal-backdrop') as Element;
    await user.pointer([
      { keys: '[MouseLeft>]', target: screen.getByRole('button', { name: 'First' }) },
      { keys: '[/MouseLeft]', target: backdrop },
    ]);

    expect(screen.queryByRole('dialog')).toBeInTheDocument();
  });

  it('returns focus to the control that opened it', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const opener = screen.getByRole('button', { name: 'Open dialog' });
    await user.click(opener);
    await user.keyboard('{Escape}');

    // Not <body>, which would restart Tab from the top of the page — the
    // thing that made logging several tiles in a row tedious.
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it('returns focus after closing from a control inside the panel', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const opener = screen.getByRole('button', { name: 'Open dialog' });
    await user.click(opener);
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(opener).toHaveFocus());
  });
});

describe('as a form', () => {
  it('submits through the panel itself', async () => {
    const user = userEvent.setup();
    render(<Harness withForm />);

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));

    // The dialog *is* the form, so its submit button is inside it rather
    // than in a wrapper one level out.
    expect(dialog().tagName).toBe('FORM');

    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(screen.getByText('Saved')).toBeInTheDocument();
  });

  it('is still a dialog, with the same trap', async () => {
    const user = userEvent.setup();
    render(<Harness withForm />);

    const behind = screen.getByRole('button', { name: 'Behind the overlay' });

    await user.click(screen.getByRole('button', { name: 'Open dialog' }));
    expect(dialog()).toHaveAttribute('aria-modal', 'true');

    for (let step = 0; step < 6; step += 1) {
      await user.tab();
      expect(behind).not.toHaveFocus();
    }
  });
});
