import { ApiError } from '../api/browser';

export type EntrySaveResult<T> =
  | { status: 'saved'; draft: string; message: string; value: T }
  | { status: 'conflict'; draft: string; message: string }
  | { status: 'error'; draft: string; message: string };

/** Save exactly the draft supplied; on a stale revision the caller keeps the draft for recovery. */
export async function saveEntryDraft<T>(
  draft: string,
  save: (personalProse: string) => Promise<T>,
): Promise<EntrySaveResult<T>> {
  try {
    const value = await save(draft);
    return { status: 'saved', draft, message: 'Entry saved.', value };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      return {
        status: 'conflict',
        draft,
        message: 'This entry changed, reload before saving.',
      };
    }
    return {
      status: 'error',
      draft,
      message: error instanceof Error ? error.message : 'Could not save this entry.',
    };
  }
}
