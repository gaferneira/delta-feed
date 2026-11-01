import type {
  GuideDefinition,
  GuideDefinitionInput,
  GuideEntry,
  GuideEntryInput,
  GuideEntryRevision,
  GuideEntryUpdate,
  GuideProposal,
} from '../guides/types';
import type { ItemsResponse } from './types';
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
