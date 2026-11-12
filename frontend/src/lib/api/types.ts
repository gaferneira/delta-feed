/** Django Ninja list envelope used by guide definitions, proposals and revisions. */
export interface ItemsResponse<T> {
  items: T[];
}

export interface EntityRef {
  name: string;
  type: string;
}

export interface FeedItem {
  article_id: number;
  url: string;
  title: string;
  excerpt: string;
  revision_number: number;
  is_read: boolean;
  is_saved: boolean;
  source_name: string | null;
  is_backfill: boolean;
  published_at: string | null;
  discovered_at: string;
  analysis_status: 'unanalysed' | 'analysed' | 'failed';
  /** Titles of the topics the article's source belongs to. */
  topics: string[];
  /** The most-mentioned known entities of the article, at most three. */
  entities: EntityRef[];
}

export interface FeedPage {
  items: FeedItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  /** Today only: articles from the last 24 hours beyond the budget. */
  more_count: number;
}

export type FeedView = 'today' | 'backfill' | 'all';

export type DeltaClassification = 'new' | 'refinement' | 'contradiction' | 'unsure';

export interface DeltaClaim {
  id: number;
  entity_name: string;
  predicate: string | null;
  value: string | null;
  claim_text: string;
  classification: DeltaClassification;
  first_sighting: boolean;
  evidence_text: string;
  matched_claim_text: string | null;
}

export interface DeltaItem extends FeedItem {
  claims: DeltaClaim[];
  /** Other articles reporting the same claims. */
  also_covered_by: number;
}

export interface MentionSummary {
  pending_groups: number;
  pending_articles: number;
}

export interface DeltaPage {
  items: DeltaItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  pending_mentions: { groups: number; articles: number };
}

export type EntityType = 'software' | 'hardware' | 'model' | 'service' | 'practice' | 'other';
export type MentionStatus = 'pending' | 'resolved' | 'dismissed';

export interface MentionCandidate {
  entity_id: number;
  name: string;
  type: EntityType;
}

export interface MentionArticle {
  article_id: number;
  title: string;
  url: string;
}

/** One group of mentions sharing a normalised name and type. */
export interface MentionGroup {
  normalized_name: string;
  name_samples: string[];
  entity_type: EntityType;
  count: number;
  article_titles: string[];
  articles: MentionArticle[];
  article_count: number;
  claim_count: number;
  evidence_sample: string;
  candidates: MentionCandidate[];
  entity_id: number | null;
  entity_name: string | null;
  decided_at: string | null;
  auto_matched: boolean;
}

export interface MentionList {
  items: MentionGroup[];
}

export type ResolveAction = 'link' | 'create' | 'dismiss';

export interface ResolveRequest {
  normalized_name: string;
  entity_type: EntityType;
  action: ResolveAction;
  entity_id?: number;
  new_entity?: { name: string; entity_type: EntityType; canonical_url?: string };
}

export interface ResolveResult {
  resolved_mentions: number;
  jobs_enqueued: number;
  entity_id: number | null;
  entity_name: string | null;
  /** Seconds the comparison is delayed after link/create; null after a dismiss (undo never expires). */
  undo_seconds: number | null;
}

export interface ResolveBatchItem extends ResolveResult {
  normalized_name: string;
  entity_type: EntityType;
  ok: boolean;
  error: string | null;
}

export interface UndoGroup {
  normalized_name: string;
  entity_type: EntityType;
}

export interface UndoItem extends UndoGroup {
  ok: boolean;
  restored_mentions: number;
  error: 'already compared' | 'nothing to undo' | null;
}
