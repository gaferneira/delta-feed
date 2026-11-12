import type {
  EntityType, MentionGroup, MentionStatus, ResolveBatchItem, ResolveRequest, ResolveResult, UndoGroup, UndoItem,
} from './api/types';

export const ENTITY_TYPES: readonly EntityType[] = ['software', 'hardware', 'model', 'service', 'practice', 'other'];
export const MAX_CANDIDATE_KEYS = 5;
/** More pending names than this shows the "large queue" hint. */
export const LARGE_QUEUE_THRESHOLD = 20;
/** Server undo windows are measured in seconds; drop the button slightly early so it never fails on click. */
export const UNDO_MARGIN_MS = 750;

export const STATUS_TABS: ReadonlyArray<{ status: MentionStatus; label: string }> = [
  { status: 'pending', label: 'To review' },
  { status: 'resolved', label: 'Tracked' },
  { status: 'dismissed', label: 'Ignored' },
];

export function parseStatus(value: string | null | undefined): MentionStatus {
  return value === 'resolved' || value === 'dismissed' ? value : 'pending';
}

export function typeLabel(type: string): string {
  return type ? type.charAt(0).toUpperCase() + type.slice(1) : 'Other';
}

export function plural(count: number, one: string, many: string = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function displayName(group: Pick<MentionGroup, 'name_samples' | 'normalized_name'>): string {
  return group.name_samples.find((sample) => sample.trim()) ?? group.normalized_name;
}

/** Other spellings seen for the same name, without repeating the displayed one. */
export function otherSpellings(group: Pick<MentionGroup, 'name_samples' | 'normalized_name'>): string[] {
  const shown = displayName(group);
  const seen = new Set<string>([shown]);
  const others: string[] = [];
  for (const sample of group.name_samples) {
    if (!sample.trim() || seen.has(sample)) continue;
    seen.add(sample);
    others.push(sample);
  }
  return others;
}

export function mentionsLabel(count: number, articles: number): string {
  return articles > 0
    ? `${plural(count, 'mention')} in ${plural(articles, 'article')}`
    : plural(count, 'mention');
}

export function claimsUnlockLabel(claimCount: number): string {
  return claimCount > 0 ? `${plural(claimCount, 'claim')} ${claimCount === 1 ? 'waits' : 'wait'} on this decision.` : '';
}

export function queueMeta(groups: number, articles: number): string {
  return `${plural(groups, 'name')} from ${plural(articles, 'article')} · most mentioned first`;
}

export function listMeta(status: MentionStatus, count: number, articles = 0): string {
  if (status === 'pending') return queueMeta(count, articles);
  return status === 'resolved'
    ? `${plural(count, 'tracked name')} · newest first`
    : `${plural(count, 'ignored name')} · newest first`;
}

export function largeQueueTitle(count: number): string {
  return `${count} names are waiting`;
}

export function isLargeQueue(count: number): boolean {
  return count > LARGE_QUEUE_THRESHOLD;
}

export function linkLabel(candidateName: string | null): string {
  return candidateName ? `Same as ${candidateName}` : 'Same as';
}

// ---------------------------------------------------------------- decisions

export type DefaultAction = 'link' | 'create';

/** Link to the first similar entity when one exists, otherwise create. */
export function defaultAction(group: Pick<MentionGroup, 'candidates'>): DefaultAction {
  return group.candidates.length > 0 ? 'link' : 'create';
}

export interface GroupRef {
  normalized_name: string;
  entity_type: EntityType;
}

export function linkPayload(group: GroupRef, entityId: number): ResolveRequest {
  return { normalized_name: group.normalized_name, entity_type: group.entity_type, action: 'link', entity_id: entityId };
}

export interface NewEntityInput {
  name: string;
  entityType: EntityType;
  homepage?: string;
}

/** Create with explicit values, or with the extracted name and type when none are given. */
export function createPayload(group: GroupRef, fallbackName: string, input?: Partial<NewEntityInput>): ResolveRequest {
  const name = (input?.name ?? '').trim() || fallbackName;
  const entityType = input?.entityType && ENTITY_TYPES.includes(input.entityType) ? input.entityType : group.entity_type;
  const homepage = (input?.homepage ?? '').trim();
  return {
    normalized_name: group.normalized_name,
    entity_type: group.entity_type,
    action: 'create',
    new_entity: { name, entity_type: entityType, ...(homepage ? { canonical_url: homepage } : {}) },
  };
}

export function dismissPayload(group: GroupRef): ResolveRequest {
  return { normalized_name: group.normalized_name, entity_type: group.entity_type, action: 'dismiss' };
}

export function undoGroups(groups: readonly GroupRef[]): UndoGroup[] {
  return groups.map((group) => ({ normalized_name: group.normalized_name, entity_type: group.entity_type }));
}

/** Groups offered by "Track all N with no similar name": pending names without any candidate. */
export function batchEligible<T extends Pick<MentionGroup, 'candidates'>>(groups: readonly T[]): T[] {
  return groups.filter((group) => group.candidates.length === 0);
}

export function batchLabel(count: number): string {
  return `Track all ${count} with no similar name`;
}

export function batchConfirmLabel(count: number): string {
  return count === 0 ? 'Nothing selected' : `Track ${plural(count, 'name')}`;
}

export function batchPayload(
  entries: ReadonlyArray<{ group: GroupRef; name: string }>,
): ResolveRequest[] {
  return entries.map(({ group, name }) => createPayload(group, name));
}

// ---------------------------------------------------------------- messages

export interface TextPart {
  text: string;
  strong?: boolean;
}

export function partsText(parts: readonly TextPart[]): string {
  return parts.map((part) => part.text).join('');
}

const quoted = (name: string): TextPart => ({ text: `“${name}”`, strong: true });
const ent = (name: string): TextPart => ({ text: name, strong: true });

function compareTail(mentions: number): string {
  return `${plural(mentions, 'mention')} resolved; ${mentions === 1 ? 'its' : 'their'} claims will be compared.`;
}

export function linkedMessage(name: string, entityName: string | null, result: Pick<ResolveResult, 'resolved_mentions'>): TextPart[] {
  return [
    quoted(name), { text: ' is now another name for ' }, ent(entityName ?? 'that entry'),
    { text: `. ${compareTail(result.resolved_mentions)}` },
  ];
}

export function createdMessage(name: string, entityName: string | null, result: Pick<ResolveResult, 'resolved_mentions'>): TextPart[] {
  return [
    { text: 'Now tracking ' }, ent(entityName ?? name),
    { text: `. ${compareTail(result.resolved_mentions)}` },
  ];
}

export function dismissedMessage(name: string, result: Pick<ResolveResult, 'resolved_mentions'>): TextPart[] {
  return [
    { text: 'Ignoring ' }, quoted(name), { text: ' from now on.' },
  ];
}

export function decisionMessage(
  action: DefaultAction | 'dismiss', name: string, result: ResolveResult,
): TextPart[] {
  if (action === 'link') return linkedMessage(name, result.entity_name, result);
  if (action === 'create') return createdMessage(name, result.entity_name, result);
  return dismissedMessage(name, result);
}

export function restoredMessage(name: string): string {
  return `“${name}” is back in To review.`;
}

export function alreadyComparedMessage(): string {
  return 'Already compared, so this can no longer be undone.';
}

export function undoFailureMessage(error: UndoItem['error'] | null): string {
  if (error === 'already compared') return alreadyComparedMessage();
  if (error === 'nothing to undo') return 'Nothing left to undo.';
  return 'Could not undo this. Try again.';
}

export function decidedElsewhereMessage(name: string): string {
  return `“${name}” was already decided elsewhere, so it was removed from this list.`;
}

export function errorMessage(status: number | null, message: string, name: string): string {
  if (status === 422 || /\[object /.test(message)) {
    return `The server rejected this decision for “${name}”. Check the name, type and homepage, then try again.`;
  }
  if (status === null) return 'Could not reach the server. Nothing was changed. Try again.';
  return message || 'Something went wrong. Nothing was changed.';
}

export interface BatchSummary {
  created: ResolveBatchItem[];
  failed: Array<{ name: string; reason: string }>;
}

export function summariseBatch(results: readonly ResolveBatchItem[], names: ReadonlyMap<string, string>): BatchSummary {
  const created: ResolveBatchItem[] = [];
  const failed: Array<{ name: string; reason: string }> = [];
  for (const result of results) {
    if (result.ok) created.push(result);
    else failed.push({
      name: names.get(`${result.entity_type}\u0000${result.normalized_name}`) ?? result.normalized_name,
      reason: result.error || 'unknown error',
    });
  }
  return { created, failed };
}

export function batchMessage(created: number, mentions: number): string {
  return `Now tracking ${plural(created, 'name')}. ${plural(mentions, 'mention')} resolved; their claims will be compared.`;
}

export function groupKey(group: GroupRef): string {
  return `${group.entity_type}\u0000${group.normalized_name}`;
}

// ---------------------------------------------------------------- keyboard

export type KeyTarget = 'field' | 'interactive' | 'radio' | 'other';

export type KeyCommand =
  | { type: 'move'; step: 1 | -1 }
  | { type: 'primary' }
  | { type: 'link' }
  | { type: 'create' }
  | { type: 'dismiss' }
  | { type: 'pick'; index: number }
  | { type: 'undo' }
  | { type: 'help' };

export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
}

/**
 * Map a key press to a command, or null when the page must leave it alone: typing in a field,
 * a modifier held, a native control that owns the key, or a request in flight for the card.
 */
export function keyCommand(event: KeyLike, target: KeyTarget, busy = false): KeyCommand | null {
  if (target === 'field') return null;
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  const key = event.key;
  if (key === '?') return { type: 'help' };
  if (event.shiftKey) return null;

  let command: KeyCommand | null = null;
  switch (key) {
    case 'ArrowDown': case 'j': command = { type: 'move', step: 1 }; break;
    case 'ArrowUp': case 'k': command = { type: 'move', step: -1 }; break;
    case 'Enter': command = { type: 'primary' }; break;
    case 's': command = { type: 'link' }; break;
    case 't': command = { type: 'create' }; break;
    case 'i': command = { type: 'dismiss' }; break;
    case 'u': command = { type: 'undo' }; break;
    default: {
      const digit = /^[1-9]$/.test(key) ? Number(key) : 0;
      if (digit >= 1 && digit <= MAX_CANDIDATE_KEYS) command = { type: 'pick', index: digit - 1 };
    }
  }
  if (!command) return null;
  // Native behaviour wins: Enter on a button, link or summary activates it; arrows move radios.
  if (command.type === 'primary' && target === 'interactive') return null;
  if (command.type === 'move' && target === 'radio' && key.startsWith('Arrow')) return null;
  if (busy && command.type !== 'move') return null;
  return command;
}

export const KEY_LIST: ReadonlyArray<{ keys: string; does: string }> = [
  { keys: '↑ ↓ or K J', does: 'Move between names' },
  { keys: 'Enter', does: 'Run the main action' },
  { keys: 'S', does: 'Same as the selected match' },
  { keys: 'T', does: 'Track this' },
  { keys: 'I', does: 'Ignore' },
  { keys: '1 – 5', does: 'Select a match' },
  { keys: 'U', does: 'Undo the last decision' },
  { keys: '?', does: 'Show or hide this list' },
];
