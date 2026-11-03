import type { APIRoute } from 'astro';
import { csrfBootstrap, proxyLogin } from '../../lib/api/server';
import { forwardSetCookies, getCsrfCookie } from '../../lib/api/session';

export const prerender = false;

export const GET: APIRoute = async ({ request }) => {
  try {
    const upstream = await csrfBootstrap(request.headers.get('cookie'));
    const headers = new Headers({
      'Cache-Control': 'private, no-store',
      'Content-Type': 'application/json',
    });
    forwardSetCookies(upstream, headers);
    if (!upstream.ok) {
      return new Response(JSON.stringify({ detail: 'Unable to prepare secure sign-in.' }), {
        status: 502,
        headers,
      });
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
  } catch {
    return new Response(JSON.stringify({ detail: 'Unable to reach the sign-in service.' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' },
    });
  }
};

export const POST: APIRoute = async ({ request }) => {
  let credentials: { username?: unknown; password?: unknown };
  try {
    credentials = await request.json();
  } catch {
    return new Response(JSON.stringify({ detail: 'Enter a username and password.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (typeof credentials.username !== 'string' || typeof credentials.password !== 'string') {
    return new Response(JSON.stringify({ detail: 'Enter a username and password.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const upstream = await proxyLogin(
      { username: credentials.username, password: credentials.password },
      request.headers.get('cookie'),
      request.headers.get('x-csrftoken') || getCsrfCookie(request.headers.get('cookie')),
    );
    const headers = new Headers({ 'Cache-Control': 'private, no-store' });
    const contentType = upstream.headers.get('content-type');
    if (upstream.status >= 300 && upstream.status < 400) {
      headers.set('Content-Type', 'application/json');
    } else if (contentType) {
      headers.set('Content-Type', contentType);
    }
    const location = upstream.headers.get('location');
    if (location) headers.set('X-Login-Redirect', location);
    // Set-Cookie is a forbidden response header to browser JavaScript, but the
    // browser stores it when this same-origin server response forwards it.
    forwardSetCookies(upstream, headers);

    if (upstream.status >= 300 && upstream.status < 400) {
      return new Response(JSON.stringify({ ok: true, redirect: location || '/' }), { status: 200, headers });
    }
    const body = upstream.status === 204 ? null : await upstream.text();
    return new Response(body, { status: upstream.status, headers });
  } catch {
    return new Response(JSON.stringify({ detail: 'Unable to reach the sign-in service.' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' },
    });
  }
};
