import type {
  GuideDefinition,
  GuideDefinitionInput,
  GuideEntry,
  GuideEntryInput,
  GuideEntryRevision,
  GuideEntryUpdate,
  GuideProposal,
} from '../guides/types';
import type { OnboardingCompletion } from '../onboarding';
import type {
  ItemsResponse, MentionSummary, ResolveBatchItem, ResolveRequest, ResolveResult, UndoGroup, UndoItem,
} from './types';
import type { Source, SourceRegistrationInput, SourceRegistrationResult } from '../sources/types';

export type FetchLike = typeof fetch;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function csrfToken(): string | undefined {
  if (typeof document === 'undefined') return undefined;
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export async function apiRequest<T = unknown>(
  path: string,
  init: RequestInit = {},
  fetcher: FetchLike = fetch,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  // A session that never passed through the sign-in page has no CSRF cookie yet;
  // fetch one before the first change instead of failing it with a 403.
  const method = (init.method ?? 'GET').toUpperCase();
  const changes = method !== 'GET' && method !== 'HEAD';
  if (changes && typeof document !== 'undefined' && !csrfToken()) {
    await fetcher('/api/accounts/csrf', { headers: { Accept: 'application/json' }, credentials: 'include' }).catch(() => undefined);
  }
  const token = csrfToken();
  if (token && !headers.has('X-CSRFToken')) headers.set('X-CSRFToken', token);

  const response = await fetcher(path, {
    ...init,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: unknown; message?: unknown; error?: unknown };
      const detail = body.detail ?? body.message ?? body.error;
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail)) message = detail.map(String).join(', ');
    } catch {
      // Keep the useful status-based fallback for empty or non-JSON responses.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface ArticleInput {
  url: string;
  title: string;
  body: string;
}

export function setArticleRead(articleId: string | number, isRead: boolean): Promise<unknown> {
  return apiRequest(`/api/reader/articles/${articleId}/read`, {
    method: 'POST',
    body: JSON.stringify({ read: isRead }),
  });
}

export function setArticleSaved(articleId: string | number, isSaved: boolean): Promise<unknown> {
  return apiRequest(`/api/reader/articles/${articleId}/save`, {
    method: 'POST',
    body: JSON.stringify({ saved: isSaved }),
  });
}

export function submitArticle(article: ArticleInput): Promise<unknown> {
  return apiRequest('/api/content/articles', {
    method: 'POST',
    body: JSON.stringify(article),
  });
}

export function listSources(fetcher?: FetchLike): Promise<Source[]> {
  return apiRequest<Source[]>('/api/content/sources', {}, fetcher);
}

export function registerSource(source: SourceRegistrationInput, fetcher?: FetchLike): Promise<SourceRegistrationResult> {
  return apiRequest<SourceRegistrationResult>('/api/content/sources', {
    method: 'POST',
    body: JSON.stringify(source),
  }, fetcher);
}

export function completeOnboarding(choices: OnboardingCompletion, fetcher?: FetchLike): Promise<unknown> {
  return apiRequest('/api/onboarding/complete', { method: 'POST', body: JSON.stringify(choices) }, fetcher);
}

export function skipOnboarding(fetcher?: FetchLike): Promise<unknown> {
  return apiRequest('/api/onboarding/skip', { method: 'POST' }, fetcher);
}

export async function listGuideDefinitions(fetcher?: FetchLike): Promise<GuideDefinition[]> {
  return (await apiRequest<ItemsResponse<GuideDefinition>>('/api/guides/definitions', {}, fetcher)).items;
}

export function getGuideDefinition(
  id: string | number,
  fetcher?: FetchLike,
): Promise<GuideDefinition> {
  return apiRequest<GuideDefinition>(
    `/api/guides/definitions/${encodeURIComponent(String(id))}`, {}, fetcher,
  );
}

export async function createGuideDefinition(
  definition: GuideDefinitionInput,
  fetcher?: FetchLike,
): Promise<GuideDefinition> {
  return apiRequest<GuideDefinition>('/api/guides/definitions', {
    method: 'POST',
    body: JSON.stringify(definition),
  }, fetcher);
}

export async function listGuideProposals(fetcher?: FetchLike): Promise<GuideProposal[]> {
  return (await apiRequest<ItemsResponse<GuideProposal>>('/api/guides/proposals', {}, fetcher)).items;
}

export function acceptGuideProposal(
  id: string | number,
  fetcher?: FetchLike,
): Promise<GuideEntry> {
  return apiRequest<GuideEntry>(`/api/guides/proposals/${encodeURIComponent(String(id))}/accept`, {
    method: 'POST',
  }, fetcher);
}

export function rejectGuideProposal(
  id: string | number,
  fetcher?: FetchLike,
): Promise<GuideProposal> {
  return apiRequest<GuideProposal>(`/api/guides/proposals/${encodeURIComponent(String(id))}/reject`, {
    method: 'POST',
  }, fetcher);
}

export async function listGuideEntries(
  guideId: string | number,
  fetcher?: FetchLike,
): Promise<GuideEntry[]> {
  const path = `/api/guides/definitions/${encodeURIComponent(String(guideId))}/entries`;
  // The backend returns a bare array here, unlike the other guide collections.
  return apiRequest<GuideEntry[]>(path, {}, fetcher);
}

export async function createGuideEntry(
  entry: GuideEntryInput,
  fetcher?: FetchLike,
): Promise<GuideEntry> {
  const { guide_id: guideId, ...payload } = entry;
  return apiRequest<GuideEntry>(
    `/api/guides/definitions/${encodeURIComponent(String(guideId))}/entries`,
    { method: 'POST', body: JSON.stringify(payload) },
    fetcher,
  );
}

export function getGuideEntry(
  id: string | number,
  fetcher?: FetchLike,
): Promise<GuideEntry> {
  return apiRequest<GuideEntry>(`/api/guides/entries/${encodeURIComponent(String(id))}`, {}, fetcher);
}

export function updateGuideEntry(
  id: string | number,
  update: GuideEntryUpdate,
  fetcher?: FetchLike,
): Promise<GuideEntry> {
  return apiRequest<GuideEntry>(`/api/guides/entries/${encodeURIComponent(String(id))}`, {
    method: 'PATCH',
    body: JSON.stringify(update),
  }, fetcher);
}

export async function getGuideEntryRevisions(
  id: string | number,
  fetcher?: FetchLike,
): Promise<GuideEntryRevision[]> {
  const payload = await apiRequest<ItemsResponse<GuideEntryRevision>>(
    `/api/guides/entries/${encodeURIComponent(String(id))}/revisions`,
    {},
    fetcher,
  );
  return payload.items;
}

export function resolveName(request: ResolveRequest, fetcher?: FetchLike): Promise<ResolveResult> {
  return apiRequest<ResolveResult>('/api/knowledge/mentions/resolve', {
    method: 'POST',
    body: JSON.stringify(request),
  }, fetcher);
}

export async function resolveNamesBatch(items: ResolveRequest[], fetcher?: FetchLike): Promise<ResolveBatchItem[]> {
  return (await apiRequest<{ results: ResolveBatchItem[] }>('/api/knowledge/mentions/resolve-batch', {
    method: 'POST',
    body: JSON.stringify({ items }),
  }, fetcher)).results;
}

export async function undoNames(groups: UndoGroup[], fetcher?: FetchLike): Promise<UndoItem[]> {
  return (await apiRequest<{ results: UndoItem[] }>('/api/knowledge/mentions/undo', {
    method: 'POST',
    body: JSON.stringify({ groups }),
  }, fetcher)).results;
}

export function getMentionSummary(fetcher?: FetchLike): Promise<MentionSummary> {
  return apiRequest<MentionSummary>('/api/knowledge/mentions/summary', {}, fetcher);
}
