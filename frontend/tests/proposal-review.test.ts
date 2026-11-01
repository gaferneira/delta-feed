import { describe, expect, it, vi } from 'vitest';
import { reviewProposal } from '../src/lib/guides/proposal-review';
import type { GuideProposal } from '../src/lib/guides/types';

const proposals: GuideProposal[] = [
  {
    id: 12,
    guide_id: 4,
    entity_id: 8,
    analysis_run_id: 3,
    source_article_id: 9,
    proposal_type: 'add',
    target_entry_id: null,
    expected_revision: null,
    proposed_entry: { entity_name: 'Example tool' },
    evidence: [],
    reasoning: 'It is a useful addition.',
    status: 'pending',
    created_at: '2026-10-30T12:00:00Z',
  },
  {
    id: 13,
    guide_id: 4,
    entity_id: 10,
    analysis_run_id: 3,
    source_article_id: 11,
    proposal_type: 'add',
    target_entry_id: null,
    expected_revision: null,
    proposed_entry: { entity_name: 'Another tool' },
    evidence: [],
    reasoning: 'It is also relevant.',
    status: 'pending',
    created_at: '2026-10-30T12:00:00Z',
  },
];

describe('guide proposal review transitions', () => {
  it('removes accepted and rejected proposals and confirms each action', async () => {
    const request = vi.fn().mockResolvedValue({});
    const accepted = await reviewProposal(proposals, 12, 'accept', request);
    const rejected = await reviewProposal(accepted.proposals, 13, 'reject', request);

    expect(accepted).toMatchObject({
      status: 'success',
      proposals: [proposals[1]],
      message: 'Proposal accepted and removed from the pending list.',
    });
    expect(rejected).toMatchObject({
      status: 'success',
      proposals: [],
      message: 'Proposal rejected and removed from the pending list.',
    });
    expect(request.mock.calls).toEqual([[12, 'accept'], [13, 'reject']]);
  });

  it('removes a proposal already processed elsewhere when the backend returns 409', async () => {
    const request = vi.fn().mockRejectedValue(Object.assign(new Error('No longer pending'), { status: 409 }));

    const result = await reviewProposal(proposals, 12, 'accept', request);

    expect(result).toMatchObject({
      status: 'already-processed',
      proposals: [proposals[1]],
      message: 'This proposal was already processed and has been removed from the pending list.',
    });
  });
});
