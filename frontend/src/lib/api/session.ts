/** Helpers shared by the same-origin session routes (login, setup). */

export function getCsrfCookie(cookie: string | null): string | undefined {
  const match = cookie?.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export function forwardSetCookies(upstream: Response, headers: Headers): void {
  const cookies = (upstream.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie?.();
  if (cookies?.length) {
    for (const cookie of cookies) headers.append('Set-Cookie', cookie);
  } else {
    const cookie = upstream.headers.get('set-cookie');
    if (cookie) headers.append('Set-Cookie', cookie);
  }
}
