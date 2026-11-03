import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAuthGate, fetchSession, type SessionPayload } from '../src/lib/auth-gate';
import {
  buildCompletion,
  createOnboardingGate,
  feedsForTopics,
  onboardingErrorMessage,
  topicStepError,
  type StarterPack,
} from '../src/lib/onboarding';

afterEach(() => vi.unstubAllGlobals());

const COOKIE = 'csrftoken=abc; sessionid=xyz';
const incomplete: SessionPayload = { authenticated: true, onboardingComplete: false };
const complete: SessionPayload = { authenticated: true, onboardingComplete: true };

function gateWith(session: SessionPayload | null) {
  const get = vi.fn(async () => session);
  return { get, gate: createOnboardingGate(get) };
}

describe('onboarding gate', () => {
  it('sends an authenticated, incomplete user to /onboarding from any page', async () => {
    const { gate } = gateWith(incomplete);
    for (const path of ['/', '/guides', '/sources', '/submit', '/login', '/setup']) {
      expect(await gate('GET', path, COOKIE)).toEqual({ action: 'redirect', location: '/onboarding' });
    }
    expect(await gate('HEAD', '/', COOKIE)).toEqual({ action: 'redirect', location: '/onboarding' });
  });

  it('renders /onboarding for an incomplete user', async () => {
    expect(await gateWith(incomplete).gate('GET', '/onboarding', COOKIE)).toEqual({ action: 'pass' });
  });

  it('lets a completed user through and sends them away from /onboarding', async () => {
    const { gate } = gateWith(complete);
    expect(await gate('GET', '/', COOKIE)).toEqual({ action: 'pass' });
    expect(await gate('GET', '/guides', COOKIE)).toEqual({ action: 'pass' });
    expect(await gate('GET', '/onboarding', COOKIE)).toEqual({ action: 'redirect', location: '/' });
  });

  it('never gates API, session routes, assets or non-page methods, and skips the lookup', async () => {
    const { gate, get } = gateWith(incomplete);
    for (const [method, path] of [
      ['GET', '/api/onboarding'], ['POST', '/api/onboarding/complete'], ['GET', '/session/login'],
      ['POST', '/session/login'], ['GET', '/_astro/app.js'], ['GET', '/favicon.ico'], ['POST', '/'], ['POST', '/guides'],
    ]) {
      expect(await gate(method, path, COOKIE)).toEqual({ action: 'pass' });
    }
    expect(get).not.toHaveBeenCalled();
  });

  it('does not look up the session for visitors without a session cookie', async () => {
    const { gate, get } = gateWith(incomplete);
    expect(await gate('GET', '/', 'csrftoken=abc')).toEqual({ action: 'pass' });
    expect(await gate('GET', '/', null)).toEqual({ action: 'pass' });
    expect(get).not.toHaveBeenCalled();
  });

  it('ignores anonymous sessions', async () => {
    const { gate } = gateWith({ authenticated: false, onboardingComplete: false });
    expect(await gate('GET', '/', COOKIE)).toEqual({ action: 'pass' });
  });

  it('fails open when the backend cannot say', async () => {
    for (const session of [null, { authenticated: true, onboardingComplete: null }]) {
      const { gate } = gateWith(session);
      expect(await gate('GET', '/', COOKIE)).toEqual({ action: 'pass' });
      expect(await gate('GET', '/onboarding', COOKIE)).toEqual({ action: 'pass' });
    }
  });

  it('shares one session lookup with the auth gate', async () => {
    const lookup = vi.fn(async (_cookie: string) => incomplete);
    let pending: Promise<SessionPayload | null> | undefined;
    const session = (cookie: string) => (pending ??= lookup(cookie));
    const auth = await createAuthGate(async (cookie) => (await session(cookie))?.authenticated ?? null)('GET', '/', '', COOKIE);
    const onboarding = await createOnboardingGate(session)('GET', '/', COOKIE);
    expect(auth).toEqual({ action: 'pass' });
    expect(onboarding).toEqual({ action: 'redirect', location: '/onboarding' });
    expect(lookup).toHaveBeenCalledTimes(1);
  });
});

describe('fetchSession', () => {
  const stub = (body: unknown, status = 200) =>
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })));

  it('maps the session payload', async () => {
    stub({ authenticated: true, onboarding_complete: false });
    expect(await fetchSession(COOKIE)).toEqual(incomplete);
    stub({ authenticated: true });
    expect(await fetchSession(COOKIE)).toEqual({ authenticated: true, onboardingComplete: null });
  });

  it('returns null on backend failure or an unexpected payload', async () => {
    stub({ detail: 'boom' }, 500);
    expect(await fetchSession(COOKIE)).toBeNull();
    stub({ nope: 1 });
    expect(await fetchSession(COOKIE)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    expect(await fetchSession(COOKIE)).toBeNull();
  });
});

const packs: StarterPack[] = [
  {
    slug: 'home', title: 'Home', description: '',
    feeds: [
      { name: 'A', feed_url: 'https://a.example/feed', homepage_url: 'https://a.example/' },
      { name: 'B', feed_url: 'https://b.example/feed', homepage_url: 'https://b.example/' },
    ],
  },
  {
    slug: 'ai', title: 'AI', description: '',
    feeds: [{ name: 'C', feed_url: 'https://c.example/feed', homepage_url: 'https://c.example/' }],
  },
];

describe('onboarding form logic', () => {
  it('lists the feeds of selected topics in pack order', () => {
    expect(feedsForTopics(packs, ['ai', 'home']).map((feed) => feed.name)).toEqual(['A', 'B', 'C']);
    expect(feedsForTopics(packs, ['nope'])).toEqual([]);
  });

  it('builds a payload from selected topics and their checked feeds only', () => {
    expect(buildCompletion(packs, ['home'], ['https://a.example/feed', 'https://c.example/feed'])).toEqual({
      topics: ['home'],
      feed_urls: ['https://a.example/feed'],
    });
  });

  it('drops unknown topics and duplicates', () => {
    expect(buildCompletion(packs, ['ai', 'ai', 'ghost'], ['https://c.example/feed', 'https://c.example/feed'])).toEqual({
      topics: ['ai'],
      feed_urls: ['https://c.example/feed'],
    });
    expect(buildCompletion(packs, [], ['https://a.example/feed'])).toEqual({ topics: [], feed_urls: [] });
  });

  it('requires a topic on step 1 and falls back to a generic error message', () => {
    expect(topicStepError([])).toMatch(/at least one topic/);
    expect(topicStepError(['home'])).toBeNull();
    expect(onboardingErrorMessage(new Error('Unknown starter pack: x'))).toBe('Unknown starter pack: x');
    expect(onboardingErrorMessage(null)).toBe('Could not save your choices.');
  });
});
