import { serverApiRequest } from './api/server';

export interface SetupState {
  /** null when the backend could not say; pages then render without redirecting. */
  needsSetup: boolean | null;
  authenticated: boolean;
}

export async function loadSetupState(cookie: string | null): Promise<SetupState> {
  const [status, session] = await Promise.all([
    serverApiRequest<{ needs_setup: boolean }>('/api/accounts/setup-status', { cookie }).catch(() => null),
    serverApiRequest<{ authenticated: boolean }>('/api/accounts/session', { cookie }).catch(() => null),
  ]);
  return {
    needsSetup: typeof status?.needs_setup === 'boolean' ? status.needs_setup : null,
    authenticated: session?.authenticated === true,
  };
}

/** Where a visitor to /setup should be sent instead, or null to render the page. */
export function setupPageRedirect(state: SetupState): string | null {
  if (state.authenticated) return '/';
  return state.needsSetup === false ? '/login' : null;
}

export type GateDecision =
  | { action: 'pass' }
  | { action: 'redirect'; location: string }
  | { action: 'deny'; status: 403; detail: string };

// Everything else is gated while setup is pending: the setup page, its submission route and build output.
const SETUP_ALLOWED_PATHS = new Set(['/setup', '/session/setup', '/favicon.ico']);
const SETUP_ALLOWED_PREFIXES = ['/_astro/'];

function isAllowedDuringSetup(pathname: string): boolean {
  return SETUP_ALLOWED_PATHS.has(pathname) || SETUP_ALLOWED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/**
 * Builds the first-run gate used by the middleware. `fetchNeedsSetup` resolves to the backend's answer, or
 * null when it cannot say. Only a completed setup (`false`) is cached for the life of the process; `true`
 * is never cached so the gate lifts as soon as the account exists, and an unreachable or failing backend
 * fails open (no redirect, no caching) so pages keep their own error handling.
 */
export function createSetupGate(fetchNeedsSetup: () => Promise<boolean | null>) {
  let setupComplete = false;
  return async (method: string, pathname: string): Promise<GateDecision> => {
    if (setupComplete || isAllowedDuringSetup(pathname)) return { action: 'pass' };
    const needsSetup = await fetchNeedsSetup();
    if (needsSetup === false) setupComplete = true;
    if (needsSetup !== true) return { action: 'pass' };
    const isPage = (method === 'GET' || method === 'HEAD') && !pathname.startsWith('/api/') && !pathname.startsWith('/session/');
    return isPage
      ? { action: 'redirect', location: '/setup' }
      : { action: 'deny', status: 403, detail: 'Setup required' };
  };
}

export async function fetchNeedsSetup(): Promise<boolean | null> {
  const status = await serverApiRequest<{ needs_setup: boolean }>('/api/accounts/setup-status').catch(() => null);
  return typeof status?.needs_setup === 'boolean' ? status.needs_setup : null;
}

export function validateSetupForm(values: {
  token: string;
  username: string;
  password: string;
  confirm: string;
}): string | null {
  if (!values.token.trim()) return 'Enter the setup token.';
  if (!values.username.trim()) return 'Choose a username.';
  if (!values.password) return 'Choose a password.';
  if (values.password !== values.confirm) return 'The passwords do not match.';
  return null;
}
