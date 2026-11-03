import { describe, expect, it } from 'vitest';
import { absoluteTime, relativeTime } from '../src/lib/time';

const now = new Date('2026-11-03T12:00:00Z');

describe('relativeTime', () => {
  it.each([
    ['2026-11-03T11:59:40Z', 'just now'],
    ['2026-11-03T12:00:30Z', 'just now'],
    ['2026-11-03T11:55:00Z', '5 min ago'],
    ['2026-11-03T10:00:00Z', '2 h ago'],
    ['2026-11-02T11:00:00Z', 'yesterday'],
    ['2026-10-31T12:00:00Z', '3 days ago'],
    ['2026-10-20T12:00:00Z', '20 Oct 2026'],
  ])('%s -> %s', (iso, expected) => {
    expect(relativeTime(iso, now)).toBe(expected);
  });

  it('returns an empty label for missing or invalid input', () => {
    expect(relativeTime(null, now)).toBe('');
    expect(relativeTime('not a date', now)).toBe('');
  });
});

describe('absoluteTime', () => {
  it('formats in UTC for the tooltip', () => {
    expect(absoluteTime('2026-11-03T10:05:00Z')).toBe('3 Nov 2026, 10:05 UTC');
    expect(absoluteTime(undefined)).toBe('');
  });
});
