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

/** A same-origin relative path safe to redirect to after sign-in; anything else falls back to "/". */
export function safeNextPath(value: unknown): string {
  if (typeof value !== 'string') return '/';
  if (!value.startsWith('/') || value.startsWith('//') || /[\\\u0000-\u001f]/.test(value)) return '/';
  return value;
}
