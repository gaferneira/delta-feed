export type GuideProposalType = 'add' | 'update' | 'warning' | 'retire';

export interface GuideProposalContent extends Record<string, unknown> {
  entity_name?: string;
  suitability?: string;
  requirements?: string[];
  caveats?: string[];
  warning?: string;
  retire?: boolean;
  reason?: string;
}

interface GuideProposalBase {
  id: number;
  guide_id: number;
  entity_id: number;
  analysis_run_id: number;
  source_article_id: number;
  target_entry_id: number | null;
  expected_revision: number | null;
  evidence: Array<Record<string, unknown>>;
  reasoning: string;
  status: string;
  created_at: string;
}

export type GuideProposal =
  | (GuideProposalBase & { proposal_type: 'add'; proposed_entry: GuideProposalContent })
  | (GuideProposalBase & { proposal_type: 'update'; proposed_entry: GuideProposalContent })
  | (GuideProposalBase & { proposal_type: 'warning'; proposed_entry: GuideProposalContent })
  | (GuideProposalBase & { proposal_type: 'retire'; proposed_entry: GuideProposalContent });

export type RevisionNumber = number;

export interface GuideSection extends Record<string, unknown> {
  title?: string;
  name?: string;
}

export interface GuideDefinition {
  id: number;
  title: string;
  purpose: string;
  audience: string;
  topic_links: string[];
  eligibility_criteria: string[];
  sections: GuideSection[];
  created_at: string;
  updated_at: string;
}

export interface GuideEntry {
  id: number;
  guide_id: number;
  entity_id: number | null;
  entity_name: string;
  suitability: string;
  requirements: string[];
  caveats: string[];
  evidence: Array<Record<string, unknown>>;
  review_metadata: Record<string, unknown>;
  personal_prose: string;
  revision: RevisionNumber;
  is_retired: boolean;
  created_at: string;
  updated_at: string;
}

export interface GuideEntryRevision {
  version: RevisionNumber;
  snapshot: { personal_prose?: string; [key: string]: unknown };
  changed_by_id: number;
  created_at: string;
}

export interface GuideDefinitionInput {
  title: string;
  purpose: string;
  audience: string;
  topic_links?: string[];
  eligibility_criteria?: string[];
  sections?: GuideSection[];
}

export interface GuideEntryInput {
  guide_id: number;
  entity_id?: number | null;
  entity_name: string;
  suitability?: string;
  requirements?: string[];
  caveats?: string[];
  evidence?: Array<Record<string, unknown>>;
  review_metadata?: Record<string, unknown>;
  personal_prose?: string;
}

export interface GuideEntryUpdate {
  personal_prose: string;
  expected_revision: RevisionNumber;
}
