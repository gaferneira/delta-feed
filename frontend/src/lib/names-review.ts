import { apiRequest, ApiError, getMentionSummary, resolveName, resolveNamesBatch, undoNames } from './api/browser';
import type { EntityType, MentionStatus, ResolveRequest, ResolveResult, UndoItem } from './api/types';
import {
  batchConfirmLabel, batchLabel, batchMessage, batchPayload, createPayload, decidedElsewhereMessage,
  decisionMessage, dismissPayload, ENTITY_TYPES, errorMessage, groupKey, isLargeQueue, keyCommand, largeQueueTitle,
  linkLabel, linkPayload, listMeta, parseStatus, partsText, plural, queueMeta, restoredMessage, summariseBatch,
  undoFailureMessage, undoGroups, UNDO_MARGIN_MS, type DefaultAction, type GroupRef, type KeyTarget, type NewEntityInput,
  type TextPart,
} from './names';

type Action = DefaultAction | 'dismiss';

interface Entry {
  ref: GroupRef;
  name: string;
  restore: () => void;
}

interface Decision {
  entries: Entry[];
  confirm: HTMLElement;
  undoable: boolean;
  undoing: boolean;
  timer: number | undefined;
  nextFocus: HTMLElement | null;
}

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function make<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function appendParts(parent: HTMLElement, parts: readonly TextPart[]): void {
  for (const part of parts) {
    if (part.strong) parent.append(make('strong', undefined, part.text));
    else parent.append(document.createTextNode(part.text));
  }
}

function groupOf(node: HTMLElement): GroupRef {
  return { normalized_name: node.dataset.name ?? '', entity_type: (node.dataset.type ?? 'other') as EntityType };
}

function targetKind(target: EventTarget | null): KeyTarget {
  if (!(target instanceof Element)) return 'other';
  if (target.closest('[data-batch], [data-edit]')) return 'field';
  const tag = target.tagName;
  if (tag === 'INPUT') return (target as HTMLInputElement).type === 'radio' ? 'radio' : 'field';
  if (tag === 'SELECT' || tag === 'TEXTAREA' || (target as HTMLElement).isContentEditable) return 'field';
  if (tag === 'BUTTON' || tag === 'A' || tag === 'SUMMARY') return 'interactive';
  return 'other';
}

function setCountBadge(anchor: Element | null, selector: string, count: number, label: string): void {
  if (!anchor) return;
  let badge = anchor.querySelector<HTMLElement>(selector);
  if (count <= 0) { badge?.remove(); return; }
  if (!badge) {
    badge = make('span', 'count');
    if (selector.startsWith('[')) badge.setAttribute(selector.slice(1, -1), '');
    anchor.append(document.createTextNode(' '), badge);
  }
  badge.textContent = String(count);
  badge.setAttribute('aria-label', `${count} ${label}`);
}

export function initNamesReview(): void {
  const page = document.querySelector<HTMLElement>('[data-names-page]');
  if (!page) return;
  const status: MentionStatus = parseStatus(page.dataset.status);
  const listNode = page.querySelector<HTMLElement>('[data-name-list]');
  const live = page.querySelector<HTMLElement>('[data-live]');
  const meta = page.querySelector<HTMLElement>('[data-meta]');
  const empty = page.querySelector<HTMLElement>('[data-empty]');
  if (!listNode) return;
  const list: HTMLElement = listNode;


  const decisions: Decision[] = [];
  const confirmMap = new WeakMap<HTMLElement, Decision>();
  let lastArticles = Number(page.dataset.articles) || 0;
  let refreshSeq = 0;
  let current: HTMLElement | null = null;

  const announce = (text: string) => {
    if (!live) return;
    // Clear first so repeating the same sentence is still announced.
    live.textContent = '';
    window.setTimeout(() => { live.textContent = text; }, 30);
  };

  // ------------------------------------------------------------ cards and focus

  const visibleCards = (): HTMLElement[] =>
    [...list.querySelectorAll<HTMLElement>('[data-name-card]')].filter((card) => !card.hidden);

  function scrollToCard(card: HTMLElement): void {
    card.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' });
  }

  function setCurrent(card: HTMLElement | null, options: { focus?: boolean; scroll?: boolean } = {}): void {
    if (current && current !== card) current.classList.remove('is-current');
    current = card;
    if (!card) return;
    card.classList.add('is-current');
    if (options.focus) card.focus({ preventScroll: true });
    if (options.scroll) scrollToCard(card);
  }

  function neighbour(card: HTMLElement): HTMLElement | null {
    const cards = visibleCards();
    const index = cards.indexOf(card);
    if (index === -1) return cards[0] ?? null;
    return cards[index + 1] ?? cards[index - 1] ?? null;
  }

  function move(step: 1 | -1): void {
    const cards = visibleCards();
    if (cards.length === 0) return;
    const index = current ? cards.indexOf(current) : -1;
    const next = index === -1 ? cards[step === 1 ? 0 : cards.length - 1] : cards[Math.min(cards.length - 1, Math.max(0, index + step))];
    setCurrent(next, { focus: true, scroll: true });
  }

  function candidateRadios(card: HTMLElement): HTMLInputElement[] {
    return [...card.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
  }

  function syncCandidate(card: HTMLElement): void {
    const radios = candidateRadios(card);
    radios.forEach((radio) => radio.closest('.opt')?.classList.toggle('sel', radio.checked));
    const checked = radios.find((radio) => radio.checked);
    const name = checked?.dataset.entityName ?? null;
    const linkButton = card.querySelector<HTMLButtonElement>('[data-act="link"]');
    if (linkButton && name) {
      const keycap = linkButton.querySelector('.kcap');
      linkButton.replaceChildren(document.createTextNode(`${linkLabel(name)} `));
      if (keycap) linkButton.append(keycap);
    }
    const help = card.querySelector<HTMLElement>('[data-link-help]');
    if (help && name) help.textContent = `“${card.dataset.display}” becomes another name for ${name}, so it matches by itself next time.`;
  }

  function pickCandidate(card: HTMLElement, index: number): void {
    const radio = candidateRadios(card)[index];
    if (!radio || radio.disabled) return;
    radio.checked = true;
    syncCandidate(card);
    announce(`Selected ${radio.dataset.entityName}.`);
  }

  // ------------------------------------------------------------ counts

  const navAnchor = () => document.querySelector('.site-header nav a[href="/names"]');
  const tabAnchor = () => document.querySelector('.tabs a');

  function applyCounts(groups: number, articles: number | null): void {
    setCountBadge(navAnchor(), '.count', groups, 'waiting');
    setCountBadge(tabAnchor(), '[data-pending-count]', groups, 'waiting');
    if (status === 'pending' && meta) {
      const n = visibleCards().length;
      if (n === 0) meta.textContent = '';
      else meta.textContent = articles !== null && groups === n ? queueMeta(n, articles) : `${plural(n, 'name')} · most mentioned first`;
    }
  }

  function syncPendingView(): void {
    const n = visibleCards().length;
    if (empty) empty.hidden = status === 'pending' ? n > 0 : list.querySelectorAll('[data-row]:not([hidden])').length > 0;
    const large = page!.querySelector<HTMLElement>('[data-large-queue]');
    if (large) {
      large.hidden = !isLargeQueue(n);
      const title = large.querySelector('[data-large-title]');
      if (title) title.textContent = largeQueueTitle(n);
    }
    syncBatch();
  }

  async function refresh(): Promise<void> {
    syncPendingView();
    const rows = list.querySelectorAll('[data-row]:not([hidden])').length;
    if (status !== 'pending' && meta) meta.textContent = rows > 0 ? listMeta(status, rows) : '';
    const n = status === 'pending' ? visibleCards().length : null;
    const seq = ++refreshSeq;
    if (n !== null) applyCounts(n, null);
    try {
      const summary = await getMentionSummary();
      if (seq !== refreshSeq) return;
      lastArticles = summary.pending_articles;
      applyCounts(summary.pending_groups, summary.pending_articles);
    } catch {
      // The optimistic local counts stay; the next page load corrects them.
      if (n !== null && meta && n > 0) meta.textContent = queueMeta(n, lastArticles);
    }
  }

  // ------------------------------------------------------------ batch disclosure

  const batch = page.querySelector<HTMLDetailsElement>('[data-batch]');
  const batchForm = page.querySelector<HTMLFormElement>('[data-batch-form]');

  const batchRows = () => [...(batch?.querySelectorAll<HTMLElement>('[data-batch-row]') ?? [])];
  const cardByKey = (key: string | undefined) => list.querySelector<HTMLElement>(`[data-name-card][data-key="${key}"]`);

  function syncBatch(): void {
    if (!batch) return;
    let available = 0;
    let ticked = 0;
    for (const row of batchRows()) {
      const card = cardByKey(row.dataset.key);
      const show = !!card && !card.hidden;
      row.hidden = !show;
      if (show) {
        available += 1;
        if (row.querySelector<HTMLInputElement>('input')?.checked) ticked += 1;
      }
    }
    batch.hidden = available < 2;
    if (available < 2) batch.open = false;
    const title = batch.querySelector('[data-batch-title]');
    if (title) title.textContent = batchLabel(available);
    const confirm = batch.querySelector<HTMLButtonElement>('[data-batch-confirm]');
    if (confirm) { confirm.textContent = batchConfirmLabel(ticked); confirm.disabled = ticked === 0; }
  }

  batchForm?.addEventListener('change', syncBatch);
  batch?.querySelector('[data-batch-cancel]')?.addEventListener('click', () => {
    batch.open = false;
    batch.querySelector<HTMLElement>('summary')?.focus();
  });

  batchForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!batch) return;
    const rows = batchRows().filter((row) => !row.hidden && row.querySelector<HTMLInputElement>('input')?.checked);
    const picked = rows.map((row) => cardByKey(row.dataset.key)).filter((card): card is HTMLElement => !!card);
    if (picked.length === 0) return;
    const button = batchForm.querySelector<HTMLButtonElement>('[data-batch-confirm]')!;
    const names = new Map<string, string>();
    const cardsByGroup = new Map<string, HTMLElement>();
    for (const card of picked) {
      const key = groupKey(groupOf(card));
      names.set(key, card.dataset.display ?? '');
      cardsByGroup.set(key, card);
    }
    batchForm.querySelector('.batch-error')?.remove();
    button.disabled = true;
    const savedLabel = button.textContent;
    button.textContent = 'Creating…';
    let results;
    try {
      results = await resolveNamesBatch(batchPayload(picked.map((card) => ({ group: groupOf(card), name: card.dataset.display ?? '' }))));
    } catch (error) {
      const alert = make('p', 'name-error batch-error', errorMessage(error instanceof ApiError ? error.status : null, error instanceof Error ? error.message : '', 'these names'));
      alert.setAttribute('role', 'alert');
      batchForm.insertBefore(alert, batchForm.querySelector('.name-form-actions'));
      button.textContent = savedLabel;
      button.disabled = false;
      return;
    }
    const summary = summariseBatch(results, names);
    const okResults = summary.created;
    const mentions = okResults.reduce((sum, r) => sum + r.resolved_mentions, 0);
    const windows = okResults.map((r) => r.undo_seconds).filter((s): s is number => typeof s === 'number' && s > 0);
    const entries: Entry[] = [];
    for (const result of okResults) {
      const card = cardsByGroup.get(groupKey(result));
      if (!card) continue;
      card.hidden = true;
      card.classList.remove('is-current');
      entries.push({ ref: groupOf(card), name: card.dataset.display ?? '', restore: () => unhide(card, false) });
    }
    batch.open = false;
    if (entries.length > 0) {
      const item = make('li', 'name-item');
      const confirm = make('div', 'card confirm');
      const text = make('p', 'meta confirm-text');
      text.append(document.createTextNode(batchMessage(entries.length, mentions)));
      confirm.append(text);
      if (summary.failed.length > 0) {
        const failures = make('ul', 'confirm-failures');
        for (const failure of summary.failed) {
          const row = make('li');
          row.append(make('strong', undefined, failure.name), document.createTextNode(`: ${failure.reason}`));
          failures.append(row);
        }
        confirm.append(make('p', 'meta confirm-text', `${plural(summary.failed.length, 'name')} could not be created and stayed in the list:`), failures);
      }
      item.append(confirm);
      list.prepend(item);
      registerDecision(confirm, entries, windows.length > 0 ? Math.min(...windows) : null, true, 'Undo all');
      announce(`${batchMessage(entries.length, mentions)}${summary.failed.length ? ` ${plural(summary.failed.length, 'name')} failed.` : ''}`);
    } else {
      const alert = make('p', 'name-error batch-error', `None of the ${plural(picked.length, 'name')} could be created: ${summary.failed.map((f) => `${f.name} (${f.reason})`).join('; ')}`);
      alert.setAttribute('role', 'alert');
      batch.append(alert);
      batch.open = true;
    }
    button.textContent = savedLabel;
    button.disabled = false;
    const next = visibleCards()[0] ?? null;
    if (next) setCurrent(next, { focus: true, scroll: true });
    else { setCurrent(null); empty?.focus?.(); }
    void refresh();
  });

  // ------------------------------------------------------------ decisions

  function unhide(card: HTMLElement, focus: boolean): void {
    card.hidden = false;
    card.querySelector('.name-error')?.remove();
    setCurrent(card, { focus, scroll: true });
  }

  function registerDecision(
    confirm: HTMLElement, entries: Entry[], undoSeconds: number | null, undoable: boolean, label = 'Undo',
  ): Decision {
    const decision: Decision = { entries, confirm, undoable, undoing: false, timer: undefined, nextFocus: null };
    confirmMap.set(confirm, decision);
    if (undoable) {
      const actions = make('div', 'confirm-actions');
      const button = make('button', 'btn2', `${label} `);
      button.type = 'button';
      button.dataset.undo = '';
      const cap = make('kbd', 'kcap', 'U');
      cap.setAttribute('aria-hidden', 'true');
      button.append(cap);
      actions.append(button);
      confirm.append(actions);
      if (undoSeconds !== null && undoSeconds > 0) {
        decision.timer = window.setTimeout(() => expire(decision), Math.max(1000, undoSeconds * 1000 - UNDO_MARGIN_MS));
      }
    }
    decisions.push(decision);
    return decision;
  }

  function closeUndo(decision: Decision): void {
    decision.undoable = false;
    window.clearTimeout(decision.timer);
    decision.confirm.querySelector('.confirm-actions')?.remove();
  }

  function expire(decision: Decision): void {
    if (!decision.undoable || decision.undoing) return;
    closeUndo(decision);
  }

  function setBusy(card: HTMLElement, on: boolean): void {
    if (on) { card.dataset.busy = '1'; card.setAttribute('aria-busy', 'true'); }
    else { delete card.dataset.busy; card.removeAttribute('aria-busy'); }
    card.classList.toggle('is-busy', on);
    card.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement>('button, input, select').forEach((control) => { control.disabled = on; });
  }

  function showError(card: HTMLElement, action: Action, status: number | null, message: string): void {
    card.querySelector('.name-error')?.remove();
    const name = card.dataset.display ?? '';
    const verb = action === 'link' ? 'link' : action === 'create' ? 'create' : 'dismiss';
    const block = make('div', 'name-error');
    block.setAttribute('role', 'alert');
    block.append(make('strong', undefined, `Couldn’t ${verb} “${name}”`), make('p', 'meta', errorMessage(status, message, name)));
    card.querySelector('.name-actions')?.before(block);
  }

  async function decide(card: HTMLElement, action: Action, input?: Partial<NewEntityInput>, trigger?: HTMLButtonElement | null): Promise<void> {
    if (card.dataset.busy === '1') return;
    const ref = groupOf(card);
    const name = card.dataset.display ?? ref.normalized_name;
    let payload: ResolveRequest;
    if (action === 'link') {
      const checked = candidateRadios(card).find((radio) => radio.checked);
      if (!checked) { announce('There is no similar name to link to. Choose Track this.'); return; }
      payload = linkPayload(ref, Number(checked.value));
    } else if (action === 'create') {
      payload = createPayload(ref, name, input);
    } else {
      payload = dismissPayload(ref);
    }

    card.querySelector('.name-error')?.remove();
    const button = trigger ?? card.querySelector<HTMLButtonElement>(`[data-act="${action}"]`);
    const saved = button ? [...button.childNodes] : [];
    setBusy(card, true);
    button?.replaceChildren(document.createTextNode('Saving…'));
    let result: ResolveResult;
    try {
      result = await resolveName(payload);
    } catch (error) {
      setBusy(card, false);
      button?.replaceChildren(...saved);
      const code = error instanceof ApiError ? error.status : null;
      if (code === 404) { removeDecidedElsewhere(card, name); return; }
      showError(card, action, code, error instanceof Error ? error.message : '');
      announce(`Couldn’t ${action} ${name}.`);
      return;
    }
    setBusy(card, false);
    button?.replaceChildren(...saved);

    const next = neighbour(card);
    const item = card.closest<HTMLElement>('[data-item]');
    const parts = decisionMessage(action, name, result);
    const confirm = make('div', 'card confirm');
    const text = make('p', 'meta confirm-text');
    appendParts(text, parts);
    confirm.append(text);
    card.hidden = true;
    card.classList.remove('is-current');
    item?.append(confirm);
    const undoable = action === 'dismiss' || (result.undo_seconds ?? 0) > 0;
    registerDecision(confirm, [{ ref, name, restore: () => unhide(card, true) }], result.undo_seconds, undoable);
    announce(partsText(parts));
    if (next) setCurrent(next, { focus: true, scroll: true });
    else { setCurrent(null); empty?.focus(); }
    void refresh();
  }

  function removeDecidedElsewhere(card: HTMLElement, name: string): void {
    const next = neighbour(card);
    const item = card.closest<HTMLElement>('[data-item]');
    const note = make('div', 'card confirm', decidedElsewhereMessage(name));
    note.classList.add('meta');
    card.hidden = true;
    card.classList.remove('is-current');
    item?.append(note);
    announce(decidedElsewhereMessage(name));
    if (next) setCurrent(next, { focus: true, scroll: true });
    else { setCurrent(null); empty?.focus(); }
    void refresh();
  }

  function createFromForm(card: HTMLElement): void {
    const form = card.querySelector<HTMLFormElement>('[data-edit-form]');
    if (!form) return;
    const nameInput = form.elements.namedItem('name') as HTMLInputElement;
    const homepage = form.elements.namedItem('homepage') as HTMLInputElement;
    const type = form.elements.namedItem('entity_type') as HTMLSelectElement;
    if (!nameInput.value.trim()) { nameInput.setCustomValidity('Enter a name.'); nameInput.reportValidity(); nameInput.setCustomValidity(''); return; }
    if (!homepage.checkValidity()) { homepage.reportValidity(); return; }
    const entityType = ENTITY_TYPES.find((t) => t === type.value) ?? (card.dataset.type as EntityType);
    void decide(card, 'create', { name: nameInput.value, entityType, homepage: homepage.value }, form.querySelector('button[type="submit"]'));
  }

  function primary(card: HTMLElement): void {
    void decide(card, card.dataset.primary === 'link' ? 'link' : 'create');
  }

  function create(card: HTMLElement): void {
    const edit = card.querySelector<HTMLDetailsElement>('[data-edit]');
    if (edit?.open) createFromForm(card);
    else void decide(card, 'create');
  }

  // ------------------------------------------------------------ undo

  async function undoDecision(decision: Decision): Promise<void> {
    if (!decision.undoable || decision.undoing) return;
    decision.undoing = true;
    const button = decision.confirm.querySelector<HTMLButtonElement>('[data-undo]');
    if (button) button.disabled = true;
    decision.confirm.classList.add('is-busy');
    let results: UndoItem[];
    try {
      results = await undoNames(undoGroups(decision.entries.map((entry) => entry.ref)));
    } catch (error) {
      decision.undoing = false;
      decision.confirm.classList.remove('is-busy');
      if (button) button.disabled = false;
      noteInConfirm(decision, errorMessage(error instanceof ApiError ? error.status : null, error instanceof Error ? error.message : '', 'this name'));
      return;
    }
    decision.undoing = false;
    decision.confirm.classList.remove('is-busy');
    const byKey = new Map(results.map((r) => [groupKey(r), r]));
    const restored = decision.entries.filter((entry) => byKey.get(groupKey(entry.ref))?.ok);
    const failed = decision.entries.filter((entry) => !byKey.get(groupKey(entry.ref))?.ok);
    restored.forEach((entry) => entry.restore());
    if (failed.length === 0) {
      window.clearTimeout(decision.timer);
      const item = decision.confirm.closest<HTMLElement>('.name-item');
      decision.confirm.remove();
      decisions.splice(decisions.indexOf(decision), 1);
      if (item && !item.querySelector('[data-name-card]')) item.remove();
      announce(restored.length === 1 ? restoredMessage(restored[0].name) : `${plural(restored.length, 'name')} ${restored.length === 1 ? 'is' : 'are'} back in To review.`);
    } else {
      const reason = byKey.get(groupKey(failed[0].ref))?.error ?? null;
      closeUndo(decision);
      const note = failed.length === decision.entries.length
        ? undoFailureMessage(reason)
        : `Restored ${plural(restored.length, 'name')}. ${plural(failed.length, 'name')} could not be undone: ${undoFailureMessage(reason).toLowerCase()}`;
      noteInConfirm(decision, note);
      decision.entries = failed;
      announce(note);
    }
    void refresh();
  }

  function noteInConfirm(decision: Decision, message: string): void {
    decision.confirm.querySelector('.confirm-note')?.remove();
    const note = make('p', 'meta confirm-note', message);
    note.setAttribute('role', 'alert');
    decision.confirm.querySelector('.confirm-actions')?.before(note);
    if (!decision.confirm.contains(note)) decision.confirm.append(note);
  }

  function undoLast(): void {
    for (let i = decisions.length - 1; i >= 0; i -= 1) {
      if (decisions[i].undoable) { void undoDecision(decisions[i]); return; }
    }
    announce('Nothing to undo.');
  }

  async function restoreRow(row: HTMLElement, trigger: HTMLButtonElement): Promise<void> {
    const name = row.dataset.display ?? '';
    trigger.disabled = true;
    row.classList.add('is-busy');
    let results: UndoItem[];
    try {
      results = await undoNames(undoGroups([groupOf(row)]));
    } catch (error) {
      trigger.disabled = false;
      row.classList.remove('is-busy');
      showRowNote(row, errorMessage(error instanceof ApiError ? error.status : null, error instanceof Error ? error.message : '', name), true);
      return;
    }
    row.classList.remove('is-busy');
    const result = results[0];
    if (result?.ok) {
      row.replaceChildren();
      row.removeAttribute('data-row');
      row.classList.add('confirm');
      const text = make('span', 'meta');
      text.append(document.createTextNode(`${restoredMessage(name)} `), make('a', undefined, 'Open To review'));
      (text.querySelector('a') as HTMLAnchorElement).href = '/names';
      row.append(text);
      announce(restoredMessage(name));
      void refresh();
    } else {
      trigger.disabled = false;
      const message = undoFailureMessage(result?.error ?? null);
      showRowNote(row, message, true);
      announce(message);
    }
  }

  function showRowNote(row: HTMLElement, message: string, alert: boolean): void {
    row.querySelector('.confirm-note')?.remove();
    const note = make('span', 'meta confirm-note', message);
    if (alert) note.setAttribute('role', 'alert');
    row.append(note);
  }

  // ------------------------------------------------------------ events

  list.addEventListener('click', (event) => {
    const target = event.target as Element;
    const card = target.closest<HTMLElement>('[data-name-card]');
    if (card && !card.hidden && card !== current) setCurrent(card);
    const act = target.closest<HTMLButtonElement>('[data-act]');
    if (act && card) {
      const action = act.dataset.act as Action;
      if (action === 'create') create(card);
      else void decide(card, action, undefined, act);
      return;
    }
    const undo = target.closest<HTMLElement>('[data-undo]');
    if (undo) {
      const decision = confirmMap.get(undo.closest<HTMLElement>('.confirm')!);
      if (decision) void undoDecision(decision);
      return;
    }
    const restore = target.closest<HTMLButtonElement>('[data-restore]');
    const row = restore?.closest<HTMLElement>('[data-row]');
    if (restore && row) { void restoreRow(row, restore); return; }
    const cancel = target.closest('[data-edit-cancel]');
    if (cancel) closeEdit(cancel.closest<HTMLDetailsElement>('[data-edit]'));
  });

  list.addEventListener('focusin', (event) => {
    const card = (event.target as Element).closest<HTMLElement>('[data-name-card]');
    if (card && !card.hidden && card !== current) setCurrent(card);
  });

  list.addEventListener('change', (event) => {
    const card = (event.target as Element).closest<HTMLElement>('[data-name-card]');
    if (card && (event.target as HTMLInputElement).type === 'radio') syncCandidate(card);
  });

  list.addEventListener('submit', (event) => {
    const form = (event.target as Element).closest<HTMLFormElement>('[data-edit-form]');
    if (!form) return;
    event.preventDefault();
    const card = form.closest<HTMLElement>('[data-name-card]');
    if (card) createFromForm(card);
  });

  // Opening the editor focuses its first field so typing can start at once.
  list.addEventListener('toggle', (event) => {
    const details = event.target as HTMLDetailsElement;
    if (details.matches?.('[data-edit]') && details.open) {
      const input = details.querySelector<HTMLInputElement>('input[name="name"]');
      input?.focus();
      input?.select();
    }
  }, true);

  function closeEdit(details: HTMLDetailsElement | null): void {
    if (!details) return;
    details.open = false;
    details.querySelector<HTMLElement>('summary')?.focus();
  }

  const panel = page.querySelector<HTMLElement>('[data-key-panel]');
  const toggle = page.querySelector<HTMLElement>('[data-key-toggle]');
  function toggleKeys(force?: boolean): void {
    if (!panel) return;
    panel.hidden = force === undefined ? !panel.hidden : !force;
    toggle?.setAttribute('aria-expanded', String(!panel.hidden));
  }
  toggle?.addEventListener('click', () => toggleKeys());

  document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || event.isComposing) return;
    if (event.key === 'Escape') {
      const edit = (event.target as Element | null)?.closest?.<HTMLDetailsElement>('[data-edit][open]') ?? null;
      if (edit) { event.preventDefault(); closeEdit(edit); return; }
      if (panel && !panel.hidden && targetKind(event.target) !== 'field') { toggleKeys(false); return; }
      return;
    }
    if (status !== 'pending') return;
    const busy = current?.dataset.busy === '1';
    const command = keyCommand(event, targetKind(event.target), busy);
    if (!command) return;

    switch (command.type) {
      case 'help': event.preventDefault(); toggleKeys(); return;
      case 'move': event.preventDefault(); move(command.step); return;
      case 'undo': event.preventDefault(); undoLast(); return;
      default: break;
    }
    if (!current || current.hidden) { if (visibleCards().length) setCurrent(visibleCards()[0], { focus: true, scroll: true }); return; }
    event.preventDefault();
    switch (command.type) {
      case 'primary': primary(current); break;
      case 'link':
        if (current.dataset.candidates === '0') announce('There is no similar name to link to. Press T to track it.');
        else void decide(current, 'link');
        break;
      case 'create': create(current); break;
      case 'dismiss': void decide(current, 'dismiss'); break;
      case 'pick': pickCandidate(current, command.index); break;
      default: break;
    }
  });

  // ------------------------------------------------------------ start

  const first = visibleCards()[0] ?? null;
  if (first) setCurrent(first);
  list.querySelectorAll<HTMLElement>('[data-name-card]').forEach(syncCandidate);
  empty?.setAttribute('tabindex', '-1');
  syncBatch();
}
