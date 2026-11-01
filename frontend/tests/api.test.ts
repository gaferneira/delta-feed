import { describe, expect, it, vi } from 'vitest';
import { proxyApiRequest } from '../src/lib/api/server';
import {
  acceptGuideProposal,
  apiRequest,
  setArticleRead,
  setArticleSaved,
  submitArticle,
} from '../src/lib/api/browser';
import { reviewProposal } from '../src/lib/guides/proposal-review';
import type { GuideProposal } from '../src/lib/guides/types';

describe('browser API client', () => {
  it('uses same-origin credentials and returns decoded JSON', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await expect(apiRequest('/api/reader/feed', {}, fetcher)).resolves.toEqual({ ok: true });
    const [, options] = fetcher.mock.calls[0];
    expect(options.credentials).toBe('include');
    expect(new Headers(options.headers).get('Accept')).toBe('application/json');
  });

  it('throws a useful message from an API error response', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not signed in' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(apiRequest('/api/reader/feed', {}, fetcher)).rejects.toThrow('Not signed in');
  });

  it('proxies browser API requests to the configured backend with session and CSRF headers', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true }), { status: 201 }),
    );
    vi.stubGlobal('fetch', fetcher);
    const request = new Request('http://frontend.test/api/content/articles?source=manual', {
      method: 'POST',
      headers: {
        cookie: 'sessionid=session-value; csrftoken=csrf-cookie; unrelated=drop-me',
        'content-type': 'application/json',
        'x-csrftoken': 'csrf-header',
      },
      body: JSON.stringify({ url: 'https://example.org/a', title: 'A', body: 'Text' }),
    });

    const response = await proxyApiRequest(request, '/api/content/articles');

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ accepted: true });
    const [url, options] = fetcher.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8000/api/content/articles?source=manual');
    expect(new Headers(options.headers).get('Cookie')).toBe('sessionid=session-value; csrftoken=csrf-cookie');
    expect(new Headers(options.headers).get('X-CSRFToken')).toBe('csrf-header');
    expect(new TextDecoder().decode(options.body as ArrayBuffer)).toBe(JSON.stringify({ url: 'https://example.org/a', title: 'A', body: 'Text' }));
    vi.unstubAllGlobals();
  });

  it('uses the backend article and reader mutation contract', async () => {
    const fetcher = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 })),
    );
    vi.stubGlobal('fetch', fetcher);

    await setArticleRead(42, true);
    await setArticleSaved(42, true);
    await submitArticle({
      url: 'https://example.org/article',
      title: 'Article title',
      body: 'Article body',
    });

    expect(fetcher.mock.calls.map(([path]) => path)).toEqual([
      '/api/reader/articles/42/read',
      '/api/reader/articles/42/save',
      '/api/content/articles',
    ]);
    expect(fetcher.mock.calls.map(([, options]) => JSON.parse(options.body as string))).toEqual([
      { read: true },
      { saved: true },
      { url: 'https://example.org/article', title: 'Article title', body: 'Article body' },
    ]);
    vi.unstubAllGlobals();
  });

  it('accepts a non-add update proposal through the shared accept endpoint', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 8, suitability: 'Updated guidance' }), { status: 200 }),
    );
    const proposal: GuideProposal = {
      id: 22,
      guide_id: 4,
      entity_id: 8,
      analysis_run_id: 3,
      source_article_id: 9,
      proposal_type: 'update',
      target_entry_id: 8,
      expected_revision: 2,
      proposed_entry: { suitability: 'Updated guidance' },
      evidence: [],
      reasoning: 'New scoped detail is available.',
      status: 'pending',
      created_at: '2026-10-30T12:00:00Z',
    };

    const result = await reviewProposal([proposal], proposal.id, 'accept', (id) =>
      acceptGuideProposal(id, fetcher),
    );

    expect(result.status).toBe('success');
    expect(result.proposals).toEqual([]);
    expect(fetcher.mock.calls[0][0]).toBe('/api/guides/proposals/22/accept');
    expect(fetcher.mock.calls[0][1].method).toBe('POST');
  });
});
