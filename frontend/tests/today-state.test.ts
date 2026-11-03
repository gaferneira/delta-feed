import { describe, expect, it } from 'vitest';
import { importProgressLabel, selectTodayEmptyState, type ImportStatus } from '../src/lib/today-state';

const status = (overrides: Partial<ImportStatus> = {}): ImportStatus => ({
  sources_total: 9,
  sources_fetched: 3,
  pending_jobs: 0,
  oldest_pending_seconds: null,
  worker_seen_recently: false,
  ...overrides,
});

describe('selectTodayEmptyState', () => {
  it('points to sources when none are registered', () => {
    expect(selectTodayEmptyState(status({ sources_total: 0, sources_fetched: 0 }))).toBe('no-sources');
  });

  it('shows importing while polls are queued and a worker is active or the wait is short', () => {
    expect(selectTodayEmptyState(status({ pending_jobs: 6, oldest_pending_seconds: 20 }))).toBe('importing');
    expect(selectTodayEmptyState(status({ pending_jobs: 6, oldest_pending_seconds: 900, worker_seen_recently: true }))).toBe('importing');
  });

  it('suggests starting the worker when old jobs wait and nothing has been processed', () => {
    expect(selectTodayEmptyState(status({ pending_jobs: 6, oldest_pending_seconds: 600 }))).toBe('worker-stopped');
  });

  it('is caught up when nothing is queued', () => {
    expect(selectTodayEmptyState(status())).toBe('caught-up');
  });

  it('degrades to caught up when the status is unavailable', () => {
    expect(selectTodayEmptyState(null)).toBe('caught-up');
  });
});

describe('importProgressLabel', () => {
  it('reports fetched sources until all are fetched', () => {
    expect(importProgressLabel(status())).toBe('3 of 9 sources fetched');
    expect(importProgressLabel(status({ sources_fetched: 9 }))).toBe('');
  });
});
