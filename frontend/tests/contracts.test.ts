import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  getGuideEntry,
  listGuideDefinitions,
  listGuideEntries,
  listGuideProposals,
  listSources,
} from '../src/lib/api/browser';
import { serverListGuideEntries, serverListGuideDefinitions, serverListSources } from '../src/lib/api/server';

afterEach(() => { vi.unstubAllGlobals(); });

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

describe('backend response contracts', () => {
  it('unwraps {items} for definitions and proposals', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(json({ items: [{ id: 1 }] })));
    expect(await listGuideDefinitions(fetcher)).toEqual([{ id: 1 }]);
    expect(await listGuideProposals(fetcher)).toEqual([{ id: 1 }]);
  });

  it('treats entries and sources as bare arrays', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(json([{ id: 2 }])));
    expect(await listGuideEntries(3, fetcher)).toEqual([{ id: 2 }]);
    expect(await listSources(fetcher)).toEqual([{ id: 2 }]);
  });

  it('does not guess alternative envelopes', async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ results: [{ id: 1 }] }));
    await expect(listGuideDefinitions(fetcher)).resolves.toBeUndefined();
  });

  it('fetches a single entry', async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ id: 5, revision: 3 }));
    expect(await getGuideEntry(5, fetcher)).toEqual({ id: 5, revision: 3 });
    expect(fetcher.mock.calls[0][0]).toBe('/api/guides/entries/5');
  });

  it('server helpers use the same shapes', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json([{ id: 1 }]))
      .mockResolvedValueOnce(json({ items: [{ id: 2 }] }))
      .mockResolvedValueOnce(json([{ id: 3 }]));
    vi.stubGlobal('fetch', fetcher);
    expect(await serverListGuideEntries(1)).toEqual([{ id: 1 }]);
    expect(await serverListGuideDefinitions()).toEqual([{ id: 2 }]);
    expect(await serverListSources()).toEqual([{ id: 3 }]);
  });
});
