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
}

export interface FeedPage {
  items: FeedItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export type FeedView = 'today' | 'backfill' | 'all';
