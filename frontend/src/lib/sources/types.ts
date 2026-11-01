export interface Source {
  id: number;
  name: string;
  rss_feed_url: string;
  last_fetch_at: string | null;
  last_error: string;
  consecutive_failures: number;
}

export interface SourceRegistrationInput {
  name: string;
  rss_feed_url: string;
}

export interface SourceRegistrationResult {
  source_id: number;
  backfill_job_id: number;
}
