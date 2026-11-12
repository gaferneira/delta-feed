import { setArticleRead, setArticleSaved } from './api/browser';

type Action = 'read' | 'save';

const MESSAGES: Record<Action, string> = {
  read: 'Marked as read.',
  save: 'Moved to your reading queue.',
};

function setState(action: Action, id: string, on: boolean): Promise<unknown> {
  return action === 'read' ? setArticleRead(id, on) : setArticleSaved(id, on);
}

function buildPlaceholder(action: Action, title: string): { root: HTMLElement; undo: HTMLButtonElement; status: HTMLElement } {
  const root = document.createElement('div');
  root.className = 'card delta-dismissed';
  root.setAttribute('role', 'status');

  const text = document.createElement('p');
  text.className = 'meta';
  const message = document.createElement('span');
  message.textContent = MESSAGES[action];
  const name = document.createElement('span');
  name.className = 'dismissed-title';
  name.textContent = title;
  text.append(message, ' ', name);

  const undo = document.createElement('button');
  undo.type = 'button';
  undo.className = 'qb';
  undo.textContent = 'Undo';

  const status = document.createElement('span');
  status.className = 'action-status';
  status.setAttribute('aria-live', 'polite');

  root.append(text, undo, status);
  return { root, undo, status };
}

/**
 * Delta cards are one-way inbox items: "Mark read" and "Save" hide the card behind a
 * placeholder with Undo, and the server leaves handled articles out of the next load.
 * The change is persisted at click time, so Undo is just the opposite request.
 */
export function initDeltaActions(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>('[data-article-card]').forEach((card) => {
    const id = card.dataset.articleId;
    if (!id) return;
    const status = card.querySelector<HTMLElement>('.action-status');

    card.querySelectorAll<HTMLButtonElement>('[data-action]').forEach((button) => {
      button.addEventListener('click', async () => {
        const action: Action = button.dataset.action === 'read' ? 'read' : 'save';
        button.disabled = true;
        if (status) status.textContent = '';
        try {
          await setState(action, id, true);
        } catch (error) {
          if (status) status.textContent = error instanceof Error ? error.message : 'Could not save this change.';
          button.disabled = false;
          return;
        }

        const title = card.querySelector('.card-title')?.textContent?.trim() ?? '';
        const placeholder = buildPlaceholder(action, title);
        card.after(placeholder.root);
        card.hidden = true;
        placeholder.undo.focus();

        placeholder.undo.addEventListener('click', async () => {
          placeholder.undo.disabled = true;
          placeholder.status.textContent = '';
          try {
            await setState(action, id, false);
          } catch (error) {
            placeholder.status.textContent = error instanceof Error ? error.message : 'Could not undo this change.';
            placeholder.undo.disabled = false;
            return;
          }
          placeholder.root.remove();
          card.hidden = false;
          button.disabled = false;
          button.focus();
        });
      });
    });
  });
}
