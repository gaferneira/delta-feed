import { afterEach, describe, expect, it, vi } from 'vitest';
import { createSetupGate, loadSetupState, setupPageRedirect, validateSetupForm } from '../src/lib/setup';
import { POST } from '../src/pages/session/setup';

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200, headers: HeadersInit = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

function post(body: unknown, headers: HeadersInit = {}) {
  return POST({
    request: new Request('http://frontend.test/session/setup', {
      method: 'POST',
      body: typeof body === 'string' ? body : JSON.stringify(body),
      headers,
    }),
  } as Parameters<typeof POST>[0]);
}

const valid = { token: 't0ken', username: 'owner', password: 'pw-1234-abcd' };

describe('setup page redirect', () => {
  it('sends /setup visitors home or to /login when setup is not available', () => {
    expect(setupPageRedirect({ needsSetup: true, authenticated: false })).toBeNull();
    expect(setupPageRedirect({ needsSetup: null, authenticated: false })).toBeNull();
    expect(setupPageRedirect({ needsSetup: false, authenticated: false })).toBe('/login');
    expect(setupPageRedirect({ needsSetup: false, authenticated: true })).toBe('/');
    expect(setupPageRedirect({ needsSetup: true, authenticated: true })).toBe('/');
  });
});

describe('setup gate', () => {
  const forbidden = { action: 'deny', status: 403, detail: 'Setup required' };

  it('redirects page requests to /setup while setup is pending', async () => {
    const gate = createSetupGate(async () => true);
    for (const path of ['/', '/login', '/guides/1', '/sources']) {
      expect(await gate('GET', path)).toEqual({ action: 'redirect', location: '/setup' });
    }
    expect(await gate('HEAD', '/')).toEqual({ action: 'redirect', location: '/setup' });
  });

  it('answers 403 JSON for API routes, session routes and non-GET requests', async () => {
    const gate = createSetupGate(async () => true);
    expect(await gate('GET', '/api/reader/feed')).toEqual(forbidden);
    expect(await gate('POST', '/api/content/sources')).toEqual(forbidden);
    expect(await gate('GET', '/session/login')).toEqual(forbidden);
    expect(await gate('POST', '/session/login')).toEqual(forbidden);
    expect(await gate('POST', '/submit')).toEqual(forbidden);
  });

  it('lets the setup page, its submission route and build output through without asking the backend', async () => {
    const lookup = vi.fn(async () => true);
    const gate = createSetupGate(lookup);
    for (const [method, path] of [['GET', '/setup'], ['GET', '/session/setup'], ['POST', '/session/setup'], ['GET', '/_astro/x.js'], ['GET', '/favicon.ico']]) {
      expect(await gate(method, path)).toEqual({ action: 'pass' });
    }
    expect(lookup).not.toHaveBeenCalled();
  });

  it('caches a completed setup and stops calling the backend', async () => {
    const lookup = vi.fn(async () => false);
    const gate = createSetupGate(lookup);
    expect(await gate('GET', '/')).toEqual({ action: 'pass' });
    expect(await gate('POST', '/api/reader/feed')).toEqual({ action: 'pass' });
    expect(lookup).toHaveBeenCalledTimes(1);
  });

  it('never caches a pending setup, so the gate lifts once the account exists', async () => {
    const lookup = vi.fn().mockResolvedValueOnce(true).mockResolvedValueOnce(true).mockResolvedValue(false);
    const gate = createSetupGate(lookup);
    expect((await gate('GET', '/')).action).toBe('redirect');
    expect((await gate('GET', '/')).action).toBe('redirect');
    expect((await gate('GET', '/')).action).toBe('pass');
    expect(lookup).toHaveBeenCalledTimes(3);
  });

  it('fails open without caching when the backend cannot say', async () => {
    const lookup = vi.fn().mockResolvedValueOnce(null).mockResolvedValue(true);
    const gate = createSetupGate(lookup);
    expect(await gate('GET', '/')).toEqual({ action: 'pass' });
    expect((await gate('GET', '/')).action).toBe('redirect');
    expect(lookup).toHaveBeenCalledTimes(2);
  });
});

describe('loadSetupState', () => {
  it('reads setup status and session, forwarding only allowlisted cookies', async () => {
    const fetcher = vi.fn(async (url: URL, _init?: RequestInit) =>
      String(url).endsWith('/setup-status') ? json({ needs_setup: true }) : json({ authenticated: false }));
    vi.stubGlobal('fetch', fetcher);
    await expect(loadSetupState('sessionid=s; other=x')).resolves.toEqual({ needsSetup: true, authenticated: false });
    for (const call of fetcher.mock.calls) {
      expect(new Headers((call[1] as RequestInit).headers).get('Cookie')).toBe('sessionid=s');
    }
  });

  it('degrades to unknown when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    await expect(loadSetupState(null)).resolves.toEqual({ needsSetup: null, authenticated: false });
  });
});

describe('setup form validation', () => {
  const base = { ...valid, confirm: valid.password };
  it('accepts a complete matching form', () => expect(validateSetupForm(base)).toBeNull());
  it('requires a matching confirmation', () =>
    expect(validateSetupForm({ ...base, confirm: 'different' })).toMatch(/do not match/));
  it.each(['token', 'username', 'password'] as const)('requires %s', (field) =>
    expect(validateSetupForm({ ...base, [field]: '' })).not.toBeNull());
});

describe('session/setup route', () => {
  it('rejects malformed or incomplete input without contacting the backend', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    expect((await post('not json')).status).toBe(400);
    expect((await post({ ...valid, token: '  ' })).status).toBe(400);
    expect((await post({ ...valid, password: 42 })).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('forwards allowlisted cookies and CSRF, and returns a home redirect plus the session cookie on success', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      json({ authenticated: true }, 200, { 'Set-Cookie': 'sessionid=new; Path=/; HttpOnly' }),
    );
    vi.stubGlobal('fetch', fetcher);

    const response = await post(valid, { cookie: 'csrftoken=abc; sessionid=old; tracker=zzz' });

    const [url, init] = fetcher.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8000/api/accounts/setup');
    const headers = new Headers(init.headers);
    expect(headers.get('Cookie')).toBe('csrftoken=abc; sessionid=old');
    expect(headers.get('X-CSRFToken')).toBe('abc');
    expect(JSON.parse(init.body)).toEqual(valid);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true, redirect: '/' });
    expect(response.headers.get('set-cookie')).toContain('sessionid=new');
  });

  it.each([[403, 'Invalid or expired setup token'], [409, 'Setup is already complete'], [429, 'Too many failed setup attempts; try again later']])(
    'passes backend %i errors through as a detail message without a session cookie', async (status, detail) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ detail }, status)));
      const response = await post(valid, { cookie: 'csrftoken=abc' });
      expect(response.status).toBe(status);
      expect(await response.json()).toEqual({ detail });
      expect(response.headers.get('set-cookie')).toBeNull();
    });

  it('returns 502 when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    expect((await post(valid)).status).toBe(502);
  });
});
