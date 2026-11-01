import { describe, expect, it } from 'vitest';
import { sourceFormError, sourceSubmissionErrorMessage } from '../src/lib/sources/form';

describe('source registration form', () => {
  it('requires a name and an absolute HTTP(S) feed URL without credentials', () => {
    expect(sourceFormError('', 'https://feeds.example.org/rss')).toBe('Enter a source name.');
    expect(sourceFormError('Example', 'ftp://feeds.example.org/rss')).toBe('Enter a valid HTTP(S) feed URL.');
    expect(sourceFormError('Example', 'https://user:pass@feeds.example.org/rss')).toBe('Enter a valid HTTP(S) feed URL.');
    expect(sourceFormError(' Example ', 'https://feeds.example.org/rss')).toBeNull();
  });

  it('shows a useful submission error and falls back for unknown failures', () => {
    expect(sourceSubmissionErrorMessage(new Error('Source name already exists'))).toBe('Source name already exists');
    expect(sourceSubmissionErrorMessage(new Error(''))).toBe('Could not register this source.');
    expect(sourceSubmissionErrorMessage('unexpected')).toBe('Could not register this source.');
  });
});
