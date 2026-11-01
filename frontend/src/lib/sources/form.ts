export function sourceFormError(name: string, feedUrl: string): string | null {
  if (!name.trim()) return 'Enter a source name.';

  try {
    const parsed = new URL(feedUrl.trim());
    if (
      !['http:', 'https:'].includes(parsed.protocol)
      || !parsed.hostname
      || parsed.username
      || parsed.password
    ) {
      return 'Enter a valid HTTP(S) feed URL.';
    }
  } catch {
    return 'Enter a valid HTTP(S) feed URL.';
  }

  return null;
}

export function sourceSubmissionErrorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim()
    ? error.message
    : 'Could not register this source.';
}
