# Authentication and Request Context Standards

This document defines constraints for user login state, server-side sessions, current-user resolution, and request context usage.

## Authentication Mode

- User login state uses Litestar `SessionAuth` by default.
- Session data is stored in Redis by default; memory store is used only for local or test scenarios.
- Cookies store only the session id; sessions store only minimal identity information, using `user_id` by default.
- The current user object uniformly uses domain schemas and does not expose database models to controllers.
- System-level APIs uniformly use the `/system` prefix and are ignored by prefix in authentication exclusion rules.

## Lifecycle

- Session expiration is controlled by authentication configuration and applies to both cookies and Redis TTL.
- When sliding expiration is required, enable access-based renewal through session configuration.
- Logout must clear the server-side session, not only delete frontend local state.
- If a user is disabled or deleted, or if session data is abnormal, treat the request as unauthenticated.

## Request Context

- When a business API needs request context, inject `ctx: RequestContext` by default.
- `RequestContext` is defined in `src/aigc/shared/context.py` and is built from `request.user` and `request.session`.
- Business code does not parse cookies or sessions directly.
- Cookies are not a business identity source; identity resolution is based on authentication middleware and session data.
- An anonymous context may exist; request rejection is handled by authentication, guards, or controllers according to interface requirements.

## Registration

- The `RequestContext` provider is registered as a global dependency through `server.plugin`.
- Runtime capabilities such as authentication middleware, Redis Store, and session backend are assembled through `server.plugin`.
- Controllers do not register global dependencies directly and do not modify application-level authentication configuration directly.
