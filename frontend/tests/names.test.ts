import { describe, expect, it } from 'vitest';
import type { MentionGroup } from '../src/lib/api/types';
import {
  batchEligible, batchMessage, batchPayload, createPayload, decisionMessage, defaultAction, dismissPayload,
  displayName, errorMessage, isLargeQueue, keyCommand, linkPayload, listMeta, mentionsLabel, otherSpellings,
  parseStatus, partsText, plural, queueMeta, summariseBatch, undoFailureMessage, undoGroups,
} from '../src/lib/names';

function group(over: Partial<MentionGroup> = {}): MentionGroup {
  return {
    normalized_name: 'senselite', name_samples: ['SenseLite', 'Sense Lite', 'senselite'], entity_type: 'software',
    count: 4, article_titles: [], articles: [], article_count: 3, claim_count: 2, evidence_sample: '',
    candidates: [], entity_id: null, entity_name: null, decided_at: null, auto_matched: false, ...over,
  };
}
const ref = { normalized_name: 'senselite', entity_type: 'software' as const };

describe('labels', () => {
  it('pluralises mentions and articles', () => {
    expect(mentionsLabel(1, 1)).toBe('1 mention in 1 article');
    expect(mentionsLabel(4, 3)).toBe('4 mentions in 3 articles');
    expect(plural(0, 'name')).toBe('0 names');
    expect(queueMeta(1, 1)).toBe('1 name from 1 article · most mentioned first');
    expect(listMeta('dismissed', 2)).toBe('2 ignored names · newest first');
  });

  it('lists other spellings without the displayed one', () => {
    expect(displayName(group())).toBe('SenseLite');
    expect(otherSpellings(group())).toEqual(['Sense Lite', 'senselite']);
    expect(displayName(group({ name_samples: [] }))).toBe('senselite');
  });

  it('parses the status tab, defaulting to pending', () => {
    expect(parseStatus('resolved')).toBe('resolved');
    expect(parseStatus('dismissed')).toBe('dismissed');
    expect(parseStatus('x')).toBe('pending');
    expect(parseStatus(null)).toBe('pending');
  });

  it('flags a large queue above 20', () => {
    expect(isLargeQueue(20)).toBe(false);
    expect(isLargeQueue(21)).toBe(true);
  });
});

describe('decisions', () => {
  it('links to the first candidate, else creates', () => {
    expect(defaultAction(group())).toBe('create');
    expect(defaultAction(group({ candidates: [{ entity_id: 1, name: 'PiSense', type: 'software' }] }))).toBe('link');
  });

  it('builds payloads for every action', () => {
    expect(linkPayload(ref, 7)).toEqual({ ...ref, action: 'link', entity_id: 7 });
    expect(dismissPayload(ref)).toEqual({ ...ref, action: 'dismiss' });
    expect(createPayload(ref, 'SenseLite')).toEqual({
      ...ref, action: 'create', new_entity: { name: 'SenseLite', entity_type: 'software' },
    });
    expect(createPayload(ref, 'SenseLite', { name: ' Sense Lite ', entityType: 'hardware', homepage: ' https://x.dev ' })).toEqual({
      ...ref, action: 'create', new_entity: { name: 'Sense Lite', entity_type: 'hardware', canonical_url: 'https://x.dev' },
    });
  });

  it('falls back to the extracted name and type for blank or unknown input', () => {
    const payload = createPayload(ref, 'SenseLite', { name: '  ', entityType: 'bogus' as never, homepage: '' });
    expect(payload.new_entity).toEqual({ name: 'SenseLite', entity_type: 'software' });
  });

  it('builds undo and batch payloads', () => {
    expect(undoGroups([{ ...ref, extra: 1 } as never])).toEqual([ref]);
    expect(batchPayload([{ group: ref, name: 'SenseLite' }])).toHaveLength(1);
  });

  it('offers only names with no similar entity for the batch', () => {
    const withCandidate = group({ normalized_name: 'a', candidates: [{ entity_id: 1, name: 'A', type: 'software' }] });
    const none = group({ normalized_name: 'b' });
    expect(batchEligible([withCandidate, none])).toEqual([none]);
  });
});

describe('messages', () => {
  const result = { resolved_mentions: 4, jobs_enqueued: 1, entity_id: 3, entity_name: 'PiSense', undo_seconds: 20 };

  it('describes each outcome', () => {
    expect(partsText(decisionMessage('link', 'SenseLite', result)))
      .toBe('“SenseLite” is now another name for PiSense. 4 mentions resolved; their claims will be compared.');
    expect(partsText(decisionMessage('create', 'GardenPi', { ...result, entity_name: 'GardenPi', resolved_mentions: 1 })))
      .toBe('Now tracking GardenPi. 1 mention resolved; its claims will be compared.');
    expect(partsText(decisionMessage('dismiss', 'the cloud', { ...result, undo_seconds: null })))
      .toContain('Ignoring “the cloud” from now on.');
  });

  it('explains undo failures plainly', () => {
    expect(undoFailureMessage('already compared')).toMatch(/already compared/i);
    expect(undoFailureMessage('nothing to undo')).toMatch(/nothing/i);
    expect(undoFailureMessage(null)).toMatch(/try again/i);
  });

  it('maps errors to readable text', () => {
    expect(errorMessage(null, '', 'X')).toMatch(/reach the server/);
    expect(errorMessage(422, 'bad', 'X')).toMatch(/rejected/);
    expect(errorMessage(500, '[object Object]', 'X')).toMatch(/rejected/);
    expect(errorMessage(500, 'Boom', 'X')).toBe('Boom');
  });

  it('summarises a batch with failures by name', () => {
    const names = new Map([['software\u0000b', 'Bee']]);
    const summary = summariseBatch([
      { normalized_name: 'a', entity_type: 'software', ok: true, resolved_mentions: 2, jobs_enqueued: 1, entity_id: 1, entity_name: 'A', undo_seconds: 20, error: null },
      { normalized_name: 'b', entity_type: 'software', ok: false, resolved_mentions: 0, jobs_enqueued: 0, entity_id: null, entity_name: null, undo_seconds: null, error: 'unknown group' },
    ], names);
    expect(summary.created).toHaveLength(1);
    expect(summary.failed).toEqual([{ name: 'Bee', reason: 'unknown group' }]);
    expect(batchMessage(3, 5)).toBe('Now tracking 3 names. 5 mentions resolved; their claims will be compared.');
  });
});

describe('keyCommand', () => {
  it('maps the documented keys', () => {
    expect(keyCommand({ key: 'j' }, 'other')).toEqual({ type: 'move', step: 1 });
    expect(keyCommand({ key: 'ArrowUp' }, 'other')).toEqual({ type: 'move', step: -1 });
    expect(keyCommand({ key: 'Enter' }, 'other')).toEqual({ type: 'primary' });
    expect(keyCommand({ key: 's' }, 'other')).toEqual({ type: 'link' });
    expect(keyCommand({ key: 't' }, 'other')).toEqual({ type: 'create' });
    expect(keyCommand({ key: 'i' }, 'other')).toEqual({ type: 'dismiss' });
    expect(keyCommand({ key: 'u' }, 'other')).toEqual({ type: 'undo' });
    for (const key of ['n', 'l', 'd']) expect(keyCommand({ key }, 'other')).toBeNull();
    expect(keyCommand({ key: '3' }, 'other')).toEqual({ type: 'pick', index: 2 });
    expect(keyCommand({ key: '?', shiftKey: true }, 'other')).toEqual({ type: 'help' });
  });

  it('ignores keys 0, 6-9 and unknown keys', () => {
    for (const key of ['0', '6', '9', 'x', ' ']) expect(keyCommand({ key }, 'other')).toBeNull();
  });

  it('ignores typing in fields and held modifiers', () => {
    expect(keyCommand({ key: 'i' }, 'field')).toBeNull();
    expect(keyCommand({ key: 'i', metaKey: true }, 'other')).toBeNull();
    expect(keyCommand({ key: 'j', ctrlKey: true }, 'other')).toBeNull();
    expect(keyCommand({ key: 'i', altKey: true }, 'other')).toBeNull();
    expect(keyCommand({ key: 'I', shiftKey: true }, 'other')).toBeNull();
  });

  it('lets native controls keep Enter and radios keep the arrows', () => {
    expect(keyCommand({ key: 'Enter' }, 'interactive')).toBeNull();
    expect(keyCommand({ key: 'j' }, 'interactive')).toEqual({ type: 'move', step: 1 });
    expect(keyCommand({ key: 'ArrowDown' }, 'radio')).toBeNull();
    expect(keyCommand({ key: 'Enter' }, 'radio')).toEqual({ type: 'primary' });
  });

  it('blocks decisions while a request is in flight but still moves and shows help', () => {
    expect(keyCommand({ key: 'i' }, 'other', true)).toBeNull();
    expect(keyCommand({ key: 'Enter' }, 'other', true)).toBeNull();
    expect(keyCommand({ key: 'j' }, 'other', true)).toEqual({ type: 'move', step: 1 });
    expect(keyCommand({ key: '?', shiftKey: true }, 'other', true)).toEqual({ type: 'help' });
  });
});
