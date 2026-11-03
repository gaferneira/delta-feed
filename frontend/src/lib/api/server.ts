import type {
  GuideDefinition,
  GuideDefinitionInput,
  GuideEntry,
  GuideEntryInput,
  GuideEntryRevision,
  GuideEntryUpdate,
  GuideProposal,
} from '../guides/types';
import type { OnboardingState } from '../onboarding';
import type { ItemsResponse } from './types';
import type { Source, SourceRegistrationInput, SourceRegistrationResult } from '../sources/types';

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

export interface ServerApiOptions {
  cookie?: string | null;
  method?: string;
  body?: string;
  headers?: HeadersInit;
}

export class ServerApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ServerApiError';
  }
}

function backendBaseUrl(): string {
  return process.env.BACKEND_URL || DEFAULT_BACKEND_URL;
}

function allowedCookieHeader(cookieHeader: string | null | undefined): string | undefined {
  if (!cookieHeader) return undefined;
  const allowed = cookieHeader.split(';').map((part) => part.trim()).filter((part) =>
    /^(sessionid|csrftoken)=/.test(part),
  );
  return allowed.length ? allowed.join('; ') : undefined;
}

export async function serverApiRequest<T>(
  path: string,
  options: ServerApiOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const cookie = allowedCookieHeader(options.cookie);
  if (cookie) headers.set('Cookie', cookie);
  headers.set('Accept', 'application/json');
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(new URL(path, backendBaseUrl()), {
    method: options.method || 'GET',
    headers,
    body: options.body,
    cache: 'no-store',
    redirect: 'manual',
  });

  if (!response.ok) {
    let message = `Backend request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: unknown; message?: unknown; error?: unknown };
      const detail = body.detail ?? body.message ?? body.error;
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail)) message = detail.map(String).join(', ');
    } catch {
      // Preserve the status-based message for non-JSON backend responses.
    }
    throw new ServerApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function backendUrl(path: string): URL {
  return new URL(path, backendBaseUrl());
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

/** The frontend's public origin, as the backend's CSRF trusted origins should list it. */
export function publicOrigin(request: Request): string {
  const configured = process.env.FRONTEND_ORIGIN || process.env.PUBLIC_ORIGIN;
  return new URL(configured || request.url).origin;
}

/** Build a backend URL for a proxied path, refusing anything outside /api/ on the configured backend. */
export function proxyTarget(path: string): URL | null {
  if (!path.startsWith('/api/')) return null;
  const segments = path.slice('/api/'.length).split('/');
  if (segments.some((segment) => segment === '' || segment === '.' || segment === '..' || /[\\\u0000-\u001f]/.test(segment))) {
    return null;
  }
  const base = backendUrl('/');
  const target = new URL(`/api/${segments.map(encodeURIComponent).join('/')}`, base);
  if (target.origin !== base.origin || !target.pathname.startsWith('/api/')) return null;
  return target;
}

export async function proxyApiRequest(request: Request, path: string): Promise<Response> {
  const target = proxyTarget(path);
  if (!target) return new Response(null, { status: 404 });

  const origin = publicOrigin(request);
  const unsafe = !SAFE_METHODS.has(request.method);
  const incomingOrigin = request.headers.get('origin');
  if (unsafe && incomingOrigin && incomingOrigin !== origin) {
    return new Response(JSON.stringify({ detail: 'Cross-origin request refused.' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' },
    });
  }

  // Only an explicit allow-list is forwarded, so hop-by-hop headers (Connection, Transfer-Encoding,
  // Upgrade, ...) and client-supplied Host/Forwarded headers never reach the backend.
  const headers = new Headers();
  const cookie = allowedCookieHeader(request.headers.get('cookie'));
  if (cookie) headers.set('Cookie', cookie);
  for (const name of ['accept', 'content-type', 'x-csrftoken']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  if (unsafe) {
    // Django's CSRF middleware validates Origin (and Referer for https) against its trusted origins.
    headers.set('Origin', origin);
    if (origin.startsWith('https:')) headers.set('Referer', `${origin}/`);
  }

  target.search = new URL(request.url).search;
  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: 'no-store',
    redirect: 'manual',
  });

  const responseHeaders = new Headers();
  for (const name of ['content-type', 'cache-control', 'vary']) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  const cookies = (upstream.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie?.();
  if (cookies?.length) {
    for (const setCookie of cookies) responseHeaders.append('Set-Cookie', setCookie);
  } else {
    const setCookie = upstream.headers.get('set-cookie');
    if (setCookie) responseHeaders.append('Set-Cookie', setCookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function csrfBootstrap(cookie?: string | null): Promise<Response> {
  const headers = new Headers({ Accept: 'text/html, application/json' });
  const forwardedCookies = allowedCookieHeader(cookie);
  if (forwardedCookies) headers.set('Cookie', forwardedCookies);
  return fetch(backendUrl(process.env.DJANGO_CSRF_PATH || '/api/accounts/csrf'), {
    method: 'GET',
    headers,
    cache: 'no-store',
    redirect: 'manual',
  });
}

export function serverListSources(cookie?: string | null): Promise<Source[]> {
  return serverApiRequest<Source[]>('/api/content/sources', { cookie });
}

export function serverRegisterSource(
  source: SourceRegistrationInput,
  cookie?: string | null,
): Promise<SourceRegistrationResult> {
  return serverApiRequest<SourceRegistrationResult>('/api/content/sources', {
    cookie, method: 'POST', body: JSON.stringify(source),
  });
}

export function serverGetOnboarding(cookie?: string | null): Promise<OnboardingState> {
  return serverApiRequest<OnboardingState>('/api/onboarding', { cookie });
}

export async function serverListGuideDefinitions(cookie?: string | null): Promise<GuideDefinition[]> {
  const payload = await serverApiRequest<ItemsResponse<GuideDefinition>>(
    '/api/guides/definitions', { cookie },
  );
  return payload.items;
}

export function serverGetGuideDefinition(
  id: string | number,
  cookie?: string | null,
): Promise<GuideDefinition> {
  return serverApiRequest<GuideDefinition>(
    `/api/guides/definitions/${encodeURIComponent(String(id))}`, { cookie },
  );
}

export function serverCreateGuideDefinition(
  definition: GuideDefinitionInput,
  cookie?: string | null,
): Promise<GuideDefinition> {
  return serverApiRequest<GuideDefinition>('/api/guides/definitions', {
    cookie, method: 'POST', body: JSON.stringify(definition),
  });
}

export async function serverListGuideProposals(cookie?: string | null): Promise<GuideProposal[]> {
  const payload = await serverApiRequest<ItemsResponse<GuideProposal>>(
    '/api/guides/proposals', { cookie },
  );
  return payload.items;
}

export function serverAcceptGuideProposal(
  id: string | number,
  cookie?: string | null,
): Promise<GuideEntry> {
  return serverApiRequest<GuideEntry>(
    `/api/guides/proposals/${encodeURIComponent(String(id))}/accept`,
    { cookie, method: 'POST' },
  );
}

export function serverRejectGuideProposal(
  id: string | number,
  cookie?: string | null,
): Promise<GuideProposal> {
  return serverApiRequest<GuideProposal>(
    `/api/guides/proposals/${encodeURIComponent(String(id))}/reject`,
    { cookie, method: 'POST' },
  );
}

export function serverListGuideEntries(
  guideId: string | number,
  cookie?: string | null,
): Promise<GuideEntry[]> {
  const path = `/api/guides/definitions/${encodeURIComponent(String(guideId))}/entries`;
  // The backend returns a bare array here, unlike the other guide collections.
  return serverApiRequest<GuideEntry[]>(path, { cookie });
}

export function serverCreateGuideEntry(
  entry: GuideEntryInput,
  cookie?: string | null,
): Promise<GuideEntry> {
  const { guide_id: guideId, ...payload } = entry;
  return serverApiRequest<GuideEntry>(
    `/api/guides/definitions/${encodeURIComponent(String(guideId))}/entries`,
    { cookie, method: 'POST', body: JSON.stringify(payload) },
  );
}

export function serverUpdateGuideEntry(
  id: string | number,
  update: GuideEntryUpdate,
  cookie?: string | null,
): Promise<GuideEntry> {
  return serverApiRequest<GuideEntry>(
    `/api/guides/entries/${encodeURIComponent(String(id))}`,
    { cookie, method: 'PATCH', body: JSON.stringify(update) },
  );
}

export async function serverListGuideEntryRevisions(
  id: string | number,
  cookie?: string | null,
): Promise<GuideEntryRevision[]> {
  const payload = await serverApiRequest<ItemsResponse<GuideEntryRevision>>(
    `/api/guides/entries/${encodeURIComponent(String(id))}/revisions`, { cookie },
  );
  return payload.items;
}

export async function proxyLogin(
  credentials: { username: string; password: string },
  cookie?: string | null,
  csrfToken?: string | null,
): Promise<Response> {
  const headers = new Headers({
    Accept: 'application/json',
    'Content-Type': 'application/json',
  });
  const forwardedCookies = allowedCookieHeader(cookie);
  if (forwardedCookies) headers.set('Cookie', forwardedCookies);
  if (csrfToken) headers.set('X-CSRFToken', csrfToken);

  return fetch(backendUrl(process.env.DJANGO_LOGIN_PATH || '/api/accounts/login'), {
    method: 'POST',
    headers,
    body: JSON.stringify(credentials),
    cache: 'no-store',
    redirect: 'manual',
  });
}

export async function proxySetup(
  input: { token: string; username: string; password: string },
  cookie?: string | null,
  csrfToken?: string | null,
): Promise<Response> {
  const headers = new Headers({
    Accept: 'application/json',
    'Content-Type': 'application/json',
  });
  const forwardedCookies = allowedCookieHeader(cookie);
  if (forwardedCookies) headers.set('Cookie', forwardedCookies);
  if (csrfToken) headers.set('X-CSRFToken', csrfToken);

  return fetch(backendUrl('/api/accounts/setup'), {
    method: 'POST',
    headers,
    body: JSON.stringify(input),
    cache: 'no-store',
    redirect: 'manual',
  });
}
