import { describe, expect, it } from 'vitest';
import { httpUrl } from '../src/lib/url';

describe('httpUrl', () => {
  it.each([
    'javascript:alert(1)',
    '  javascript:alert(1)',
    'java\tscript:alert(1)',
    '\njavascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:x',
    'ftp://example.org/file',
    '/relative/path',
    '//example.org/x',
    'not a url',
    '',
  ])('rejects %j', (value) => {
    expect(httpUrl(value)).toBeNull();
  });

  it('rejects non-strings', () => {
    expect(httpUrl(undefined)).toBeNull();
    expect(httpUrl(null)).toBeNull();
    expect(httpUrl(42)).toBeNull();
  });

  it('accepts http and https URLs', () => {
    expect(httpUrl('https://example.org/a?b=1')).toBe('https://example.org/a?b=1');
    expect(httpUrl('http://example.org')).toBe('http://example.org/');
    expect(httpUrl('  https://example.org/x  ')).toBe('https://example.org/x');
  });
});
