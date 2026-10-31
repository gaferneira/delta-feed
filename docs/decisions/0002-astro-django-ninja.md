# ADR 0002: Astro SSR reader with Django Ninja API

**Status:** Accepted; implementation and version compatibility unverified.

## Context

The reader is content-first: mostly server-rendered cards and articles with a little interactivity (read/save/feedback). The backend needs a typed JSON API while keeping Django's ORM, migrations, authentication and admin.

## Decision

Use Astro SSR + TypeScript and CSS for the reader, with small browser scripts/islands where needed; React is optional. Use Django Ninja JSON endpoints as thin adapters around Django-backed domain behavior and worker use cases.

One repo with frontend/ and backend/: a separate frontend image/runtime and a shared backend API/worker image. Generic Compose provides same-origin routing and needs no host-specific infrastructure. Django owns sessions and authorization; browser and Astro SSR use explicit authenticated API paths. Frontend API types are generated from Ninja OpenAPI; runtime payloads are validated where needed.

Private news renders on demand, never as build-time personalized pages. Sessions and secrets stay out of browser props and shared caches. Installed-version CSRF behavior is tested, especially login and session-authenticated mutations. Authentication is a real integration task, not an automatic consequence of same-origin deployment.

## Alternatives

- Django templates + HTMX: one runtime and no API/auth coordination, but less suited to a component-structured, content-focused frontend.
- React SPA / Next.js: richer persistent client state, which the reader does not need; reconsider if offline or rich client interaction becomes central.
- FastAPI or DRF: unnecessary alongside Django Ninja with Django ORM/auth.

## Trade-offs

Adds a Node build/runtime and API/auth coordination. Astro is chosen for frontend structure and selective interactivity, not for processing or database throughput. This ADR does not approve implementation scaffolding.

## First proof

Exercise login → persisted article → Astro SSR feed → Django Ninja save/read → persisted reload, plus missing/invalid CSRF, session expiry, unauthorized access, generated-type build from a clean checkout, and private-cache isolation. No AI needed for this slice.
