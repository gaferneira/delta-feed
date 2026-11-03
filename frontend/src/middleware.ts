import { defineMiddleware } from 'astro:middleware';
import { createAuthGate, fetchSessionAuthenticated } from './lib/auth-gate';
import { createSetupGate, fetchNeedsSetup } from './lib/setup';

const gate = createSetupGate(fetchNeedsSetup);
const authGate = createAuthGate(fetchSessionAuthenticated);

export const onRequest = defineMiddleware(async ({ request, url, redirect }, next) => {
  const decision = await gate(request.method, url.pathname);
  if (decision.action === 'redirect') return redirect(decision.location, 302);
  if (decision.action === 'deny') {
    return new Response(JSON.stringify({ detail: decision.detail }), {
      status: decision.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' },
    });
  }
  const auth = await authGate(request.method, url.pathname, url.search, request.headers.get('cookie'));
  if (auth.action === 'redirect') return redirect(auth.location, 302);
  return next();
});
