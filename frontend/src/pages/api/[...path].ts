import type { APIRoute } from 'astro';
import { proxyApiRequest } from '../../lib/api/server';

export const prerender = false;

const proxy: APIRoute = async ({ request, params }) => {
  const path = String(params.path || '');
  if (!path) return new Response(null, { status: 404 });

  try {
    return await proxyApiRequest(request, `/api/${path}`);
  } catch {
    return new Response(JSON.stringify({ detail: 'Unable to reach the API service.' }), {
      status: 502,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'private, no-store',
      },
    });
  }
};

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
