import { describe, expect, it, vi } from 'vitest';
import { createAuthGate, hasSessionCookie, loginLocation } from '../src/lib/auth-gate';
import { createSetupGate } from '../src/lib/setup';
import { safeNextPath } from '../src/lib/url';

const COOKIE = 'csrftoken=abc; sessionid=xyz';

function gateWith(result: boolean | null) {
  const check = vi.fn(async () => result);
  return { check, gate: createAuthGate(check) };
}

describe('safeNextPath', () => {
  it.each(['//evil.com', 'https://evil.com', '/\\evil.com', 'javascript:alert(1)', '', 'guides', '/a\nb', null, undefined])(
    'rejects %j',
    (value) => expect(safeNextPath(value)).toBe('/'),
  );
  it.each(['/', '/guides?x=1', '/guides/3#top'])('accepts %s', (value) => expect(safeNextPath(value)).toBe(value));
});

describe('hasSessionCookie', () => {
  it('detects the session cookie by exact name', () => {
    expect(hasSessionCookie(COOKIE)).toBe(true);
    expect(hasSessionCookie('xsessionid=1')).toBe(false);
    expect(hasSessionCookie('csrftoken=abc')).toBe(false);
    expect(hasSessionCookie(null)).toBe(false);
  });
});

describe('auth gate', () => {
  it('redirects without calling the backend when there is no session cookie', async () => {
    const { gate, check } = gateWith(true);
    expect(await gate('GET', '/guides', '?x=1&y=2', 'csrftoken=abc')).toEqual({
      action: 'redirect',
      location: '/login?next=%2Fguides%3Fx%3D1%26y%3D2',
    });
    expect(await gate('GET', '/', '', null)).toEqual({ action: 'redirect', location: '/login?next=%2F' });
    expect(check).not.toHaveBeenCalled();
  });

  it('redirects when the backend says the session is not authenticated', async () => {
    const { gate, check } = gateWith(false);
    expect(await gate('GET', '/guides', '', COOKIE)).toEqual({ action: 'redirect', location: '/login?next=%2Fguides' });
    expect(check).toHaveBeenCalledWith(COOKIE);
  });

  it('passes an authenticated session', async () => {
    const { gate } = gateWith(true);
    expect(await gate('GET', '/guides', '', COOKIE)).toEqual({ action: 'pass' });
    expect(await gate('HEAD', '/', '', COOKIE)).toEqual({ action: 'pass' });
  });

  it('fails open when the backend cannot say', async () => {
    const { gate } = gateWith(null);
    expect(await gate('GET', '/guides', '', COOKIE)).toEqual({ action: 'pass' });
  });

  it('leaves public pages, assets, API and session routes alone', async () => {
    const { gate, check } = gateWith(false);
    for (const [method, path] of [
      ['GET', '/login'], ['GET', '/setup'], ['GET', '/favicon.ico'], ['GET', '/_astro/app.js'],
      ['GET', '/api/reader/feed'], ['POST', '/api/reader/read'], ['GET', '/session/login'], ['POST', '/session/login'],
      ['POST', '/guides'],
    ]) {
      expect(await gate(method, path, '', COOKIE)).toEqual({ action: 'pass' });
    }
    expect(await gate('GET', '/login', '', null)).toEqual({ action: 'pass' });
    expect(await gate('GET', '/setup', '', null)).toEqual({ action: 'pass' });
    expect(check).toHaveBeenCalledTimes(1); // only the /login visit that carried a cookie
  });

  it('sends an already signed-in visitor of /login to a validated next or /', async () => {
    const { gate } = gateWith(true);
    expect(await gate('GET', '/login', '?next=%2Fguides%3Fx%3D1', COOKIE)).toEqual({ action: 'redirect', location: '/guides?x=1' });
    expect(await gate('GET', '/login', '?next=%2F%2Fevil.com', COOKIE)).toEqual({ action: 'redirect', location: '/' });
    expect(await gate('GET', '/login', '', COOKIE)).toEqual({ action: 'redirect', location: '/' });
  });

  it('renders /login when the session is stale or the backend is unsure', async () => {
    expect(await gateWith(false).gate('GET', '/login', '', COOKIE)).toEqual({ action: 'pass' });
    expect(await gateWith(null).gate('GET', '/login', '', COOKIE)).toEqual({ action: 'pass' });
  });

  it('builds an encoded login location', () => {
    expect(loginLocation('/a b', '?q=1')).toBe('/login?next=%2Fa%20b%3Fq%3D1');
  });

  it('is evaluated after the setup gate, which takes precedence', async () => {
    const setup = createSetupGate(async () => true);
    const { gate, check } = gateWith(false);
    const decision = await setup('GET', '/guides');
    expect(decision).toEqual({ action: 'redirect', location: '/setup' });
    // The middleware returns on a non-pass setup decision, so the auth gate is never consulted.
    if (decision.action === 'pass') await gate('GET', '/guides', '', COOKIE);
    expect(check).not.toHaveBeenCalled();
  });
});
