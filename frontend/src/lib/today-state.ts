export interface ImportStatus {
  sources_total: number;
  sources_fetched: number;
  pending_jobs: number;
  oldest_pending_seconds: number | null;
  worker_seen_recently: boolean;
}

export type TodayEmptyState = 'no-sources' | 'importing' | 'worker-stopped' | 'caught-up';

/** How long a queued poll may wait with no sign of a worker before we suggest starting one. */
export const WORKER_STALL_SECONDS = 180;

export const WORKER_COMMAND = 'cd backend && DJANGO_DEBUG=true uv run python manage.py run_worker';

/** Which message an empty Today shows. A missing status degrades to the neutral "caught up". */
export function selectTodayEmptyState(status: ImportStatus | null): TodayEmptyState {
  if (!status) return 'caught-up';
  if (status.sources_total === 0) return 'no-sources';
  if (status.pending_jobs > 0) {
    const waited = status.oldest_pending_seconds ?? 0;
    return !status.worker_seen_recently && waited >= WORKER_STALL_SECONDS ? 'worker-stopped' : 'importing';
  }
  return 'caught-up';
}

/** "3 of 9 sources fetched", or '' once everything has been fetched. */
export function importProgressLabel(status: ImportStatus): string {
  if (status.sources_total === 0 || status.sources_fetched >= status.sources_total) return '';
  return `${status.sources_fetched} of ${status.sources_total} sources fetched`;
}
