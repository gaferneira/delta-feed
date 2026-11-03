const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
});

/** "2 h ago" style label; older than a week falls back to the date. Empty for an invalid value. */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  const then = iso ? new Date(iso) : null;
  if (!then || Number.isNaN(then.getTime())) return '';
  const age = now.getTime() - then.getTime();
  if (age < MINUTE) return 'just now';
  if (age < HOUR) return `${Math.floor(age / MINUTE)} min ago`;
  if (age < DAY) return `${Math.floor(age / HOUR)} h ago`;
  if (age < 7 * DAY) {
    const days = Math.floor(age / DAY);
    return days === 1 ? 'yesterday' : `${days} days ago`;
  }
  return dateFormat.format(then);
}

/** Absolute timestamp for tooltips, always in UTC so server and tests agree. */
export function absoluteTime(iso: string | null | undefined): string {
  const then = iso ? new Date(iso) : null;
  if (!then || Number.isNaN(then.getTime())) return '';
  return `${dateTimeFormat.format(then)} UTC`;
}
