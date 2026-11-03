/** Django Ninja list envelope used by guide definitions, proposals and revisions. */
export interface ItemsResponse<T> {
  items: T[];
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
