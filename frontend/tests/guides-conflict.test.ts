import { describe, expect, it, vi } from 'vitest';
import { updateGuideEntry } from '../src/lib/api/browser';
import { saveEntryDraft } from '../src/lib/guides/edit';

describe('guide entry conflict handling', () => {
  it('moves to conflict on 409 and keeps the unsaved draft intact', async () => {
    const draft = 'My unsaved personal note';
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Revision conflict' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await saveEntryDraft(draft, (personalProse) =>
      updateGuideEntry('entry-7', {
        personal_prose: personalProse,
        expected_revision: 4,
      }, fetcher),
    );

    expect(result).toEqual({
      status: 'conflict',
      draft,
      message: 'This entry changed, reload before saving.',
    });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(JSON.parse(fetcher.mock.calls[0][1].body as string)).toEqual({
      personal_prose: draft,
      expected_revision: 4,
    });
  });
});
