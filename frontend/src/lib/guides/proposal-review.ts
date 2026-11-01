export type ProposalReviewAction = 'accept' | 'reject';
export type ProposalReviewStatus = 'success' | 'already-processed' | 'error';

export interface ProposalReviewItem {
  id: string | number;
}

export interface ProposalReviewState<T extends ProposalReviewItem> {
  proposals: T[];
  status: ProposalReviewStatus;
  message: string;
}

export type ProposalReviewRequest = (
  proposalId: string | number,
  action: ProposalReviewAction,
) => Promise<unknown>;

export async function reviewProposal<T extends ProposalReviewItem>(
  proposals: T[],
  proposalId: string | number,
  action: ProposalReviewAction,
  request: ProposalReviewRequest,
): Promise<ProposalReviewState<T>> {
  try {
    await request(proposalId, action);
    return {
      proposals: proposals.filter((proposal) => String(proposal.id) !== String(proposalId)),
      status: 'success',
      message: action === 'accept'
        ? 'Proposal accepted and removed from the pending list.'
        : 'Proposal rejected and removed from the pending list.',
    };
  } catch (error) {
    if (typeof error === 'object' && error !== null && 'status' in error && error.status === 409) {
      return {
        proposals: proposals.filter((proposal) => String(proposal.id) !== String(proposalId)),
        status: 'already-processed',
        message: 'This proposal was already processed and has been removed from the pending list.',
      };
    }
    return {
      proposals,
      status: 'error',
      message: 'We could not update this proposal. Please try again.',
    };
  }
}
