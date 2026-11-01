/** Return a normalised absolute http(s) URL, or null for anything else (javascript:, data:, relative, malformed). */
export function httpUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  try {
    const parsed = new URL(value.trim());
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
  } catch {
    return null;
  }
}
