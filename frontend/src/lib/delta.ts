import type { DeltaClaim, DeltaClassification } from './api/types';

export const MAX_SHOWN_CLAIMS = 5;

const KIND_LABELS: Record<DeltaClassification, string> = {
  new: 'New',
  refinement: 'Changed',
  contradiction: 'Conflicts',
  unsure: 'Not sure',
};
const KIND_CLASSES: Record<DeltaClassification, string> = {
  new: 'k-new',
  refinement: 'k-chg',
  contradiction: 'k-con',
  unsure: 'k-uns',
};

export function kindLabel(classification: DeltaClassification): string {
  return KIND_LABELS[classification] ?? KIND_LABELS.unsure;
}

export function kindClass(classification: DeltaClassification): string {
  return KIND_CLASSES[classification] ?? KIND_CLASSES.unsure;
}

export interface ClaimGroups {
  /** Sure claims always visible. */
  shown: DeltaClaim[];
  /** Sure claims beyond the fifth, behind "+N more". */
  collapsed: DeltaClaim[];
  /** "Not sure" claims. */
  unsure: DeltaClaim[];
  /** Open the unsure group only when the card has nothing else to show. */
  unsureOpen: boolean;
}

export function splitClaims(claims: readonly DeltaClaim[]): ClaimGroups {
  const sure = claims.filter((claim) => claim.classification !== 'unsure');
  const unsure = claims.filter((claim) => claim.classification === 'unsure');
  return {
    shown: sure.slice(0, MAX_SHOWN_CLAIMS),
    collapsed: sure.slice(MAX_SHOWN_CLAIMS),
    unsure,
    unsureOpen: sure.length === 0,
  };
}

export interface ClaimParts {
  /** Muted attribute label, or null when the claim has no structured form. */
  label: string | null;
  text: string;
}

export function claimParts(claim: Pick<DeltaClaim, 'predicate' | 'value' | 'claim_text'>): ClaimParts {
  const label = claim.predicate?.trim();
  const value = claim.value?.trim();
  if (label && value) return { label, text: value };
  return { label: null, text: claim.claim_text };
}

/** "You knew" for a matched baseline claim; "Could match" when the model was unsure. */
export function matchLabel(classification: DeltaClassification): string {
  return classification === 'unsure' ? 'Could match' : 'You knew';
}

export function unsureSummary(count: number): string {
  return `Show ${count} ${count === 1 ? 'claim' : 'claims'} we are not sure about`;
}

export function alsoCoveredLabel(count: number): string {
  return `Also covered by ${count} other ${count === 1 ? 'article' : 'articles'}`;
}

export function namesWaitingLabel(groups: number, articles: number): string {
  const names = `${groups} ${groups === 1 ? 'name' : 'names'}`;
  const from = `${articles} ${articles === 1 ? 'article' : 'articles'}`;
  return `${names} from ${from} ${groups === 1 ? 'is' : 'are'} waiting for review`;
}

export type DeltaEmptyState = 'names-waiting' | 'nothing';

/** With no cards: names still waiting explain it; otherwise there is simply nothing yet. */
export function selectDeltaEmptyState(pendingGroups: number): DeltaEmptyState {
  return pendingGroups > 0 ? 'names-waiting' : 'nothing';
}

export function rangeLabel(offset: number, count: number, total: number): string {
  if (count === 0) return `Showing 0 of ${total} cards`;
  return `Showing ${offset + 1}–${offset + count} of ${total} cards`;
}
