import { setArticleRead, setArticleSaved } from './api/browser';

const DEFAULT_LABELS = {
  read: { on: 'Mark unread', off: 'Mark read' },
  save: { on: 'Unsave', off: 'Save' },
} as const;

/**
 * Wire the read/save buttons of every `[data-article-card]` on the page. Buttons carry
 * `data-action="read|save"` and `aria-pressed`; optional `data-label-on` / `data-label-off`
 * override the label shown for each state.
 */
export function initArticleActions(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>('[data-article-card]').forEach((card) => {
    const id = card.dataset.articleId;
    if (!id) return;

    card.querySelectorAll<HTMLButtonElement>('[data-action]').forEach((button) => {
      button.addEventListener('click', async () => {
        const action = button.dataset.action === 'read' ? 'read' : 'save';
        const status = card.querySelector<HTMLElement>('.action-status');
        const indicator = card.querySelector<HTMLElement>(action === 'read' ? '[data-read-indicator]' : '[data-save-indicator]');
        const wasActive = button.getAttribute('aria-pressed') === 'true';
        button.disabled = true;
        if (status) status.textContent = '';

        try {
          const next = !wasActive;
          if (action === 'read') await setArticleRead(id, next);
          else await setArticleSaved(id, next);

          button.setAttribute('aria-pressed', String(next));
          button.textContent = next
            ? (button.dataset.labelOn ?? DEFAULT_LABELS[action].on)
            : (button.dataset.labelOff ?? DEFAULT_LABELS[action].off);
          if (action === 'read') {
            card.classList.toggle('is-read', next);
            card.querySelectorAll<HTMLElement>('[data-read-chip]').forEach((chip) => { chip.hidden = !next; });
          }
          if (indicator) {
            indicator.textContent = action === 'read' ? (next ? 'Read' : 'Unread') : (next ? 'Saved' : 'Not saved');
            indicator.classList.toggle('active', next);
          }
        } catch (error) {
          if (status) status.textContent = error instanceof Error ? error.message : 'Could not save this change.';
        } finally {
          button.disabled = false;
        }
      });
    });
  });
}
