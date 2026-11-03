import { serverApiRequest } from './api/server';
import { safeNextPath } from './url';

export type AuthDecision = { action: 'pass' } | { action: 'redirect'; location: string };

const PUBLIC_PATHS = new Set(['/login', '/setup', '/favicon.ico']);
const PUBLIC_PREFIXES = ['/_astro/'];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.has(pathname) || PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function loginLocation(pathname: string, search = ''): string {
  return `/login?next=${encodeURIComponent(pathname + search)}`;
}

export function hasSessionCookie(cookie: string | null): boolean {
  return /(?:^|;\s*)sessionid=[^;\s]+/.test(cookie ?? '');
}

/**
 * Builds the sign-in gate that runs after the setup gate. `checkSession` resolves to the backend's
 * verdict for the cookie, or null when it cannot say; an unreachable or failing backend fails open so
 * pages keep their own error handling. API and session routes are never redirected: the backend's 401
 * stays authoritative there.
 */
export function createAuthGate(checkSession: (cookie: string) => Promise<boolean | null>) {
  return async (method: string, pathname: string, search: string, cookie: string | null): Promise<AuthDecision> => {
    const isPage = (method === 'GET' || method === 'HEAD') && !pathname.startsWith('/api/') && !pathname.startsWith('/session/');
    if (!isPage || (pathname !== '/login' && isPublic(pathname))) return { action: 'pass' };
    const signedIn = hasSessionCookie(cookie) ? await checkSession(cookie as string) : false;
    if (pathname === '/login') {
      // Already signed in: skip the form. Anything uncertain renders the form.
      return signedIn === true
        ? { action: 'redirect', location: safeNextPath(new URLSearchParams(search).get('next')) }
        : { action: 'pass' };
    }
    if (signedIn !== false) return { action: 'pass' };
    return { action: 'redirect', location: loginLocation(pathname, search) };
  };
}

export interface SessionPayload {
  authenticated: boolean;
  /** null when the backend did not report it. */
  onboardingComplete: boolean | null;
}

/** The session verdict for a cookie, or null when the backend cannot say. */
export async function fetchSession(cookie: string): Promise<SessionPayload | null> {
  const session = await serverApiRequest<{ authenticated: boolean; onboarding_complete?: boolean }>(
    '/api/accounts/session',
    { cookie },
  ).catch(() => null);
  if (typeof session?.authenticated !== 'boolean') return null;
  return {
    authenticated: session.authenticated,
    onboardingComplete: typeof session.onboarding_complete === 'boolean' ? session.onboarding_complete : null,
  };
}
