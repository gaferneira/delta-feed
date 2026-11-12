import { describe, expect, it } from 'vitest';
import type { DeltaClaim } from '../src/lib/api/types';
import {
  alsoCoveredLabel, claimParts, kindClass, kindLabel, matchLabel, namesWaitingLabel,
  rangeLabel, selectDeltaEmptyState, splitClaims,
} from '../src/lib/delta';

function claim(id: number, classification: DeltaClaim['classification'] = 'new'): DeltaClaim {
  return {
    id, entity_name: 'HubCore', predicate: 'zigbee', value: 'GA in 3.0', claim_text: 'Zigbee is GA in 3.0',
    classification, first_sighting: false, evidence_text: '', matched_claim_text: null,
  };
}

describe('kind labels', () => {
  it('maps every classification to a label and chip class', () => {
    expect(kindLabel('new')).toBe('New');
    expect(kindLabel('refinement')).toBe('Changed');
    expect(kindLabel('contradiction')).toBe('Conflicts');
    expect(kindLabel('unsure')).toBe('Not sure');
    expect(kindClass('refinement')).toBe('k-chg');
    expect(kindClass('unsure')).toBe('k-uns');
  });
});

describe('splitClaims', () => {
  it('keeps up to five sure claims and collapses the rest', () => {
    const groups = splitClaims(Array.from({ length: 7 }, (_, i) => claim(i)));
    expect(groups.shown).toHaveLength(5);
    expect(groups.collapsed.map((c) => c.id)).toEqual([5, 6]);
  });

  it('does not collapse exactly five', () => {
    expect(splitClaims(Array.from({ length: 5 }, (_, i) => claim(i))).collapsed).toEqual([]);
  });

  it('closes the unsure group when other claims exist', () => {
    const groups = splitClaims([claim(1), claim(2, 'unsure')]);
    expect(groups.unsure).toHaveLength(1);
    expect(groups.unsureOpen).toBe(false);
  });

  it('opens the unsure group when it is all the card has', () => {
    const groups = splitClaims([claim(1, 'unsure')]);
    expect(groups.shown).toEqual([]);
    expect(groups.unsureOpen).toBe(true);
  });
});

describe('claimParts', () => {
  it('splits attribute and value', () => {
    expect(claimParts(claim(1))).toEqual({ label: 'zigbee', text: 'GA in 3.0' });
  });

  it('falls back to the claim text when either part is missing', () => {
    expect(claimParts({ predicate: null, value: 'x', claim_text: 'full' })).toEqual({ label: null, text: 'full' });
    expect(claimParts({ predicate: 'p', value: null, claim_text: 'full' })).toEqual({ label: null, text: 'full' });
  });
});

describe('labels and states', () => {
  it('words the baseline match by confidence', () => {
    expect(matchLabel('refinement')).toBe('You knew');
    expect(matchLabel('unsure')).toBe('Could match');
  });

  it('pluralises counts', () => {
    expect(alsoCoveredLabel(1)).toBe('Also covered by 1 other article');
    expect(alsoCoveredLabel(4)).toBe('Also covered by 4 other articles');
    expect(namesWaitingLabel(1, 1)).toBe('1 name from 1 article is waiting for review');
    expect(namesWaitingLabel(7, 5)).toBe('7 names from 5 articles are waiting for review');
  });

  it('picks the empty state', () => {
    expect(selectDeltaEmptyState(3)).toBe('names-waiting');
    expect(selectDeltaEmptyState(0)).toBe('nothing');
  });

  it('labels the shown range', () => {
    expect(rangeLabel(25, 16, 41)).toBe('Showing 26–41 of 41 cards');
    expect(rangeLabel(0, 0, 0)).toBe('Showing 0 of 0 cards');
  });
});
