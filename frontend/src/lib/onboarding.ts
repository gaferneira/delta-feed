import { hasSessionCookie, type SessionPayload } from './auth-gate';

export interface StarterFeed {
  name: string;
  feed_url: string;
  homepage_url: string;
}

export interface StarterPack {
  slug: string;
  title: string;
  description: string;
  feeds: StarterFeed[];
}

export interface OnboardingState {
  packs: StarterPack[];
  selected_topics: string[];
}

export interface OnboardingCompletion {
  topics: string[];
  feed_urls: string[];
}

export type OnboardingDecision = { action: 'pass' } | { action: 'redirect'; location: string };

export const ONBOARDING_PATH = '/onboarding';

// Build output and the favicon are never gated, so the onboarding page can load its own assets.
const ASSET_PATHS = new Set(['/favicon.ico']);
const ASSET_PREFIXES = ['/_astro/'];

/**
 * Builds the onboarding gate that runs after the setup and auth gates. `getSession` resolves to the
 * session payload for the cookie, or null when the backend cannot say; the middleware shares one lookup
 * with the auth gate. Anything uncertain fails open. API and session routes are never redirected.
 */
export function createOnboardingGate(getSession: (cookie: string) => Promise<SessionPayload | null>) {
  return async (method: string, pathname: string, cookie: string | null): Promise<OnboardingDecision> => {
    const isPage = (method === 'GET' || method === 'HEAD') && !pathname.startsWith('/api/') && !pathname.startsWith('/session/');
    if (!isPage || ASSET_PATHS.has(pathname) || ASSET_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
      return { action: 'pass' };
    }
    if (!hasSessionCookie(cookie)) return { action: 'pass' };
    const session = await getSession(cookie as string);
    if (session?.authenticated !== true || typeof session.onboardingComplete !== 'boolean') return { action: 'pass' };
    if (pathname === ONBOARDING_PATH) {
      return session.onboardingComplete ? { action: 'redirect', location: '/' } : { action: 'pass' };
    }
    return session.onboardingComplete ? { action: 'pass' } : { action: 'redirect', location: ONBOARDING_PATH };
  };
}

/** Feeds of the selected packs, in pack order, as shown on step 2. */
export function feedsForTopics(packs: StarterPack[], topics: string[]): StarterFeed[] {
  const selected = new Set(topics);
  return packs.filter((pack) => selected.has(pack.slug)).flatMap((pack) => pack.feeds);
}

/**
 * The payload for "Finish": only selected topics, and only checked feeds that belong to them
 * (the backend rejects anything else). Order and duplicates are normalized.
 */
export function buildCompletion(packs: StarterPack[], topics: string[], checkedFeedUrls: string[]): OnboardingCompletion {
  const known = new Set(packs.map((pack) => pack.slug));
  const chosen = [...new Set(topics)].filter((slug) => known.has(slug));
  const checked = new Set(checkedFeedUrls);
  const feedUrls = feedsForTopics(packs, chosen).map((feed) => feed.feed_url).filter((url) => checked.has(url));
  return { topics: chosen, feed_urls: [...new Set(feedUrls)] };
}

export function topicStepError(topics: string[]): string | null {
  return topics.length ? null : 'Pick at least one topic, or skip for now.';
}

export function onboardingErrorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim() ? error.message : 'Could not save your choices.';
}
