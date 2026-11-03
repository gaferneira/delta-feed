import type { APIRoute } from 'astro';
import { csrfBootstrap, proxySetup } from '../../lib/api/server';
import { forwardSetCookies, getCsrfCookie } from '../../lib/api/session';

export const prerender = false;

const JSON_HEADERS = { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' };

export const GET: APIRoute = async ({ request }) => {
  try {
    const upstream = await csrfBootstrap(request.headers.get('cookie'));
    const headers = new Headers(JSON_HEADERS);
    forwardSetCookies(upstream, headers);
    if (!upstream.ok) {
      return new Response(JSON.stringify({ detail: 'Unable to prepare secure setup.' }), { status: 502, headers });
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
  } catch {
    return new Response(JSON.stringify({ detail: 'Unable to reach the setup service.' }), {
      status: 502,
      headers: JSON_HEADERS,
    });
  }
};

export const POST: APIRoute = async ({ request }) => {
  let input: { token?: unknown; username?: unknown; password?: unknown };
  try {
    input = await request.json();
  } catch {
    input = {};
  }

  if (
    typeof input.token !== 'string' || !input.token.trim()
    || typeof input.username !== 'string' || !input.username.trim()
    || typeof input.password !== 'string' || !input.password
  ) {
    return new Response(JSON.stringify({ detail: 'Enter the setup token, a username and a password.' }), {
      status: 400,
      headers: JSON_HEADERS,
    });
  }

  try {
    const upstream = await proxySetup(
      { token: input.token, username: input.username, password: input.password },
      request.headers.get('cookie'),
      request.headers.get('x-csrftoken') || getCsrfCookie(request.headers.get('cookie')),
    );
    const headers = new Headers(JSON_HEADERS);
    // The session cookie set by the backend is stored by the browser from this same-origin response.
    forwardSetCookies(upstream, headers);

    if (upstream.ok) {
      return new Response(JSON.stringify({ ok: true, redirect: '/' }), { status: 200, headers });
    }
    // Surface only the backend's human-readable detail, never its raw body.
    let detail = 'Setup failed.';
    try {
      const body = await upstream.json() as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Keep the generic message for non-JSON backend responses.
    }
    return new Response(JSON.stringify({ detail }), { status: upstream.status, headers });
  } catch {
    return new Response(JSON.stringify({ detail: 'Unable to reach the setup service.' }), {
      status: 502,
      headers: JSON_HEADERS,
    });
  }
};
