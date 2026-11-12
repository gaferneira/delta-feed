export interface DismissAction {
  /** Shown in the placeholder once the card is gone. */
  message: string;
  /** Persist the change; `on` is false when the user undoes it. */
  apply: (articleId: string, on: boolean) => Promise<unknown>;
}

function buildPlaceholder(messageText: string, title: string): { root: HTMLElement; undo: HTMLButtonElement; status: HTMLElement } {
  const root = document.createElement('div');
  root.className = 'card dismissed-card';
  root.setAttribute('role', 'status');

  const text = document.createElement('p');
  text.className = 'meta';
  const message = document.createElement('span');
  message.textContent = messageText;
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
 * Inbox-style cards: a `[data-dismiss="<name>"]` button inside a `[data-article-card]` hides the
 * card behind a placeholder with Undo, and the server leaves handled articles out of the next
 * load. The change is persisted at click time, so Undo is just the opposite request.
 */
export function initDismissActions(actions: Record<string, DismissAction>, root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>('[data-article-card]').forEach((card) => {
    const id = card.dataset.articleId;
    if (!id) return;
    const status = card.querySelector<HTMLElement>('.action-status');

    card.querySelectorAll<HTMLButtonElement>('[data-dismiss]').forEach((button) => {
      if (!actions[button.dataset.dismiss ?? '']) return;
      button.addEventListener('click', async () => {
        // Resolved at click time: the page may flip a button between "read" and "unread".
        const action = actions[button.dataset.dismiss ?? ''];
        if (!action) return;
        button.disabled = true;
        if (status) status.textContent = '';
        try {
          await action.apply(id, true);
        } catch (error) {
          if (status) status.textContent = error instanceof Error ? error.message : 'Could not save this change.';
          button.disabled = false;
          return;
        }

        const title = card.querySelector('h2')?.textContent?.trim() ?? '';
        const placeholder = buildPlaceholder(action.message, title);
        card.after(placeholder.root);
        card.hidden = true;
        placeholder.undo.focus();

        placeholder.undo.addEventListener('click', async () => {
          placeholder.undo.disabled = true;
          placeholder.status.textContent = '';
          try {
            await action.apply(id, false);
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
