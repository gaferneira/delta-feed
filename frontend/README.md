# Frontend runtime notes

The frontend is an Astro SSR Node application. Personalized routes are rendered on demand and send `Cache-Control: private, no-store`; no feed content or account data is included in static assets.

Set `BACKEND_URL` in the server runtime to the trusted Django service origin (for example, `http://api:8000`). It is server-only: do not prefix it with `PUBLIC_`. The server client forwards only the `sessionid` and `csrftoken` cookies. The login relay obtains a CSRF cookie from `DJANGO_CSRF_PATH` (default `/api/accounts/csrf`), posts JSON credentials to `DJANGO_LOGIN_PATH` (default `/api/accounts/login`), and relays upstream `Set-Cookie` headers to the browser. The Astro `/api/[...path]` route proxies browser API requests to the configured backend while forwarding only the session/CSRF cookies and CSRF header.

The browser API uses same-origin requests with credentials and sends `X-CSRFToken` when Django's `csrftoken` cookie exists. The exercised backend contract for this slice is:

- `GET /api/accounts/csrf` returns `csrf_token` and sets the CSRF cookie; `POST /api/accounts/login` accepts `username` and `password`, and sets a Django session cookie.
- `GET /api/reader/feed` returns `{ "items": [...] }`; each item has `article_id`, `title`, `url`, `body`, `revision_number`, `is_read` and `is_saved`.
- `POST /api/content/articles` accepts `{ "url": "...", "title": "...", "body": "..." }`.
- `POST /api/reader/articles/{article_id}/read` accepts `{ "read": true|false }`.
- `POST /api/reader/articles/{article_id}/save` accepts `{ "saved": true|false }`.

The browser submission carries supplied article text, consistent with the `provided_content` body requirement in `docs/ingestion-contract.md`. The documented `/api/v1/ingestions` collector contract remains a design proposal and is not the browser endpoint in this milestone slice.
