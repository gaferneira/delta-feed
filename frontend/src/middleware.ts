import { defineMiddleware } from 'astro:middleware';
import { createAuthGate, fetchSession, type SessionPayload } from './lib/auth-gate';
import { createOnboardingGate } from './lib/onboarding';
import { createSetupGate, fetchNeedsSetup } from './lib/setup';

const gate = createSetupGate(fetchNeedsSetup);

export const onRequest = defineMiddleware(async ({ request, url, redirect }, next) => {
  const decision = await gate(request.method, url.pathname);
  if (decision.action === 'redirect') return redirect(decision.location, 302);
  if (decision.action === 'deny') {
    return new Response(JSON.stringify({ detail: decision.detail }), {
      status: decision.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' },
    });
  }
  // The auth and onboarding gates read the same session, so a page request makes one backend call.
  let lookup: Promise<SessionPayload | null> | undefined;
  const session = (cookie: string) => (lookup ??= fetchSession(cookie));
  const auth = await createAuthGate(async (cookie) => (await session(cookie))?.authenticated ?? null)(
    request.method, url.pathname, url.search, request.headers.get('cookie'),
  );
  if (auth.action === 'redirect') return redirect(auth.location, 302);
  const onboarding = await createOnboardingGate(session)(request.method, url.pathname, request.headers.get('cookie'));
  if (onboarding.action === 'redirect') return redirect(onboarding.location, 302);
  return next();
});
