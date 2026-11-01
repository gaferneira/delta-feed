import { afterEach, describe, expect, it, vi } from 'vitest';
import { proxyApiRequest, proxyTarget } from '../src/lib/api/server';

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.FRONTEND_ORIGIN;
});

function stubFetch() {
  const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

describe('proxy target validation', () => {
  it.each(['/api/', '/api/../admin', '/api/a/../b', '/api//evil.test/x', '/api/a//b', '/api/./a', '/api/a\\b', '/other/x', '//evil.test/api/x'])(
    'refuses %s', (path) => expect(proxyTarget(path)).toBeNull(),
  );

  it('keeps valid paths on the configured backend', () => {
    expect(String(proxyTarget('/api/guides/entries/4'))).toBe('http://127.0.0.1:8000/api/guides/entries/4');
  });

  it('returns 404 without contacting the backend for traversal paths', async () => {
    const fetcher = stubFetch();
    const response = await proxyApiRequest(new Request('http://frontend.test/api/x'), '/api/../admin');
    expect(response.status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe('proxy headers', () => {
  it('sends the public Origin and Referer on unsafe methods and drops hop-by-hop headers', async () => {
    const fetcher = stubFetch();
    process.env.FRONTEND_ORIGIN = 'https://feed.example.org';
    await proxyApiRequest(new Request('http://internal:4321/api/guides/entries/4', {
      method: 'DELETE',
      headers: {
        cookie: 'sessionid=s; csrftoken=c; other=x',
        'x-csrftoken': 'tok',
        connection: 'keep-alive',
        'x-forwarded-for': '1.2.3.4',
        host: 'evil.test',
        origin: 'https://feed.example.org',
      },
    }), '/api/guides/entries/4');

    const headers = new Headers(fetcher.mock.calls[0][1].headers);
    expect(fetcher.mock.calls[0][1].method).toBe('DELETE');
    expect(headers.get('Origin')).toBe('https://feed.example.org');
    expect(headers.get('Referer')).toBe('https://feed.example.org/');
    expect(headers.get('X-CSRFToken')).toBe('tok');
    expect(headers.get('Cookie')).toBe('sessionid=s; csrftoken=c');
    expect(headers.has('connection')).toBe(false);
    expect(headers.has('x-forwarded-for')).toBe(false);
    expect(headers.get('host')).toBeNull();
  });

  it('derives Origin from the request URL and omits Referer for http', async () => {
    const fetcher = stubFetch();
    await proxyApiRequest(new Request('http://localhost:4321/api/reader/articles/1/read', { method: 'POST', body: '{}' }), '/api/reader/articles/1/read');
    const headers = new Headers(fetcher.mock.calls[0][1].headers);
    expect(headers.get('Origin')).toBe('http://localhost:4321');
    expect(headers.has('Referer')).toBe(false);
  });

  it('refuses unsafe requests from a foreign Origin', async () => {
    const fetcher = stubFetch();
    const response = await proxyApiRequest(new Request('http://localhost:4321/api/x', {
      method: 'PATCH', headers: { origin: 'https://evil.test' }, body: '{}',
    }), '/api/x');
    expect(response.status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('does not add Origin to safe requests', async () => {
    const fetcher = stubFetch();
    await proxyApiRequest(new Request('http://localhost:4321/api/reader/feed?view=today'), '/api/reader/feed');
    const [url, options] = fetcher.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8000/api/reader/feed?view=today');
    expect(new Headers(options.headers).has('Origin')).toBe(false);
  });
});
