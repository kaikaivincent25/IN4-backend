# IN4 FastAPI Backend Design

## Purpose and compatibility target

This document describes a FastAPI replacement for the current Django REST
backend. It is based on the Django models, serializers, views, and the mobile
app's API client. It is a design document only; Django and the app have not
been changed by this document.

The mobile client currently sends requests to `${API_BASE_URL}/api` (the
Android emulator setting is `http://10.0.2.2:8000`). Preserve the `/api`
prefix, trailing slashes, snake_case JSON keys, status codes, and response
envelopes below so the backend can be swapped without broad screen changes.
The relevant client is [in4-mobile/src/api/client.js](./in4-mobile/src/api/client.js).

## Suggested FastAPI structure

Use separate modules for routers, ORM models, request/response schemas,
authentication, and domain services. Keep business transactions in services
rather than duplicating them across route handlers.

```text
backend/
  app/
    main.py
    api/
      auth.py
      experts.py
      articles.py
      categories.py
      engagements.py
    core/
      config.py
      security.py
      dependencies.py
    db/
      session.py
      models/
      schemas/
    services/
      auth.py
      articles.py
      engagements.py
  alembic/
```

Recommended implementation components: FastAPI, SQLAlchemy 2.x, Pydantic
request/response schemas, Alembic migrations, and the existing PostgreSQL
database. Configure secrets and database credentials through environment
variables; do not put credentials in source control. Keep OpenAPI available at
FastAPI's `/docs` and `/openapi.json` (or expose compatibility aliases at
`/api/docs/` and `/api/schema/` if deployment tooling depends on the Django
paths).

## Data model

Use integer primary keys for compatibility with IDs already returned by
Django and passed by the mobile app. Preserve the current relationships,
uniqueness rules, and status values. The table names below are Django's
conventional names and are useful if reusing its existing database.

| Entity (table) | Fields and constraints |
|---|---|
| **User** (`users_customuser`) | `id`; unique, indexed `email`; password hash (never serialize); `first_name`, `last_name`; `is_consumer` (default true), `is_provider` (default false); `is_active`, `is_staff`, `is_superuser` for account state/admin; `created_at`, `updated_at`. Email is the login identifier. |
| **Category** (`categories_category`) | `id`; unique `name`, `slug`, and `content_type`; `description`; `content_type` enum: `medical`, `legal`, `financial`, `technology`, `mental`, `agriculture`, `general`; `icon_name`, `color_code`, `order`, `is_active`; timestamps. |
| **CategoryTemplate** (`categories_categorytemplate`) | `id`; unique `category_id` FK; `template_json` JSON, default `{}`. Optional category detail data. |
| **Expert** (`experts_expert`) | `id`; unique `user_id` FK; `profession`; `license_number`, `license_issuer`; `bio`, `expertise_areas`, `organization`; `status` (`pending`, `verified`, `rejected`); `badge_tier` (`verified`, `credentialed`, `institutional`); nullable `verified_by_id` FK and `verified_at`; `rejection_reason`; unique `slug`; timestamps. Add indexes for `status`, `profession`, and `slug`. A verified expert sets the user's `is_provider` true; pending/rejected experts do not. |
| **Article** (`articles_article`) | `id`; `author_id` FK to User; `category_id` FK to Category; `title` (10–200 chars); `summary` (20–500 chars); `body` (minimum 100 chars); nullable `featured_image` URL; `status` (`draft`, `published`, `archived`); unique `slug`; non-negative `view_count`, `save_count`; `created_at`, `updated_at`, nullable `published_at`. Index status/published date, author, and category. |
| **ArticleDraft** (`articles_articledraft`) | `id`; `author_id` FK; nullable, unique `article_id` FK for a draft of an existing article; `title`, `summary`, `body`; nullable `category_id` FK; nullable `featured_image`; `version` (starts at 1); `is_auto_saved`; `created_at`, `updated_at`, nullable `last_auto_save`. Keep drafts incomplete until publication validation. Store `category_id` as a real FK rather than the current unconstrained integer. |
| **SavedArticle** (`engagements_savedarticle`) | `id`; `user_id` FK; `article_id` FK; `saved_at`; unique constraint on `(user_id, article_id)`; indexes on user and saved date. |
| **ReadHistory** (`engagements_readhistory`) | `id`; `user_id` FK; `article_id` FK; `read_at`; unique constraint on `(user_id, article_id)`; indexes on user and read date. Re-reading updates `read_at` rather than adding a duplicate. |
| **ArticleStats** (`engagements_articlestats`) | `id`; unique `article_id` FK; `total_saves`, `total_reads`, `unique_readers`, `engagement_score`; timestamps. Update atomically with engagement writes, or derive from source records if choosing not to retain this cache. |

Use cascading deletes for user-owned content, drafts, saves, and history, as in
Django. Category deletion should be restricted while articles reference it.
Generate slugs uniquely and set `published_at` on first publication.
`reading_time` is a computed integer: at least 1 minute, based on body word
count at approximately 200 words per minute. Do not trust client-supplied
author, status, counts, verification fields, or timestamps.

## API contract

All paths below are under `/api` and retain the trailing slash. Protected
routes require `Authorization: Bearer <access-token>`. Public routes are
explicitly marked.

### Health

| Method and path | Access | Response |
|---|---|---|
| `GET /health/` | Public | `200`: `{status: "ok"}`. Checks that the FastAPI process is responding; it does not check database availability. |

### Authentication and account

| Method and path | Access | Request | Response |
|---|---|---|---|
| `POST /auth/register/` | Public | `email`, `password`, `password_confirm`, `first_name`, `last_name` | `201`: `{status, message, user, tokens: {access, refresh}}`. Require matching passwords, unique normalized email, minimum 8 characters, and reject all-numeric or all-alphabetic passwords as current Django validation does. |
| `POST /auth/login/` | Public | `email`, `password` | `200`: `{status, message, user, tokens: {access, refresh}}`. Reject inactive accounts. |
| `POST /auth/token/refresh/` | Public | `{refresh}` | `200`: `{status: "success", access}`. The app's interceptor expects the new access token at `response.data.access`. |
| `GET /auth/profile/` | User | — | `200`: `{status: "success", user}`. |
| `PUT /auth/profile/` | User | Optional `first_name`, `last_name` | `200`: `{status, message, user}`. |
| `POST /auth/change-password/` | User | `old_password`, `new_password`, `new_password_confirm` | `200`: `{status, message}`; verify the old password and matching new-password fields. |
| `POST /auth/logout/` | User, optional | — | `{status, message}`. The current mobile client only clears local tokens and does not call this route. |

User responses must not include password hashes:

```json
{
  "id": 12,
  "email": "person@example.com",
  "first_name": "Ari",
  "last_name": "Example",
  "is_consumer": true,
  "is_provider": false,
  "created_at": "2026-10-16T11:00:00Z",
  "updated_at": "2026-10-16T11:00:00Z"
}
```

Registration/login's nested `user` may use the smaller current public shape
(`id`, `email`, `first_name`, `last_name`, `is_provider`, `created_at`).
Profile returns the full shape above.

### Experts

| Method and path | Access | Request/query | Response |
|---|---|---|---|
| `GET /experts/` | Public | Optional `profession`, `search`, `page` | Paginated verified experts. |
| `GET /experts/{slug}/` | Public | — | Verified public profile. Include `name`, `profession`, `profession_display`, `bio`, `expertise_areas`, `organization`, `badge_tier`, `badge_display`, `article_count`, `verified_at`, and `articles` (published article-list objects). |
| `POST /experts/apply/` | User | `profession`, `license_number`, `license_issuer`, optional `bio`, `expertise_areas`, `organization` | `201`: `{status: "success", message, expert_id, application_status: "pending"}`. A user may apply only once. |
| `GET /experts/me/` | Verified provider | — | `{status: "success", expert}` with the expert's own profile fields, including verification status. |
| `PUT /experts/me/` | Verified provider | `bio`, `expertise_areas`, `organization` | `{status, message, expert}`. Do not allow changing profession, license details, badge, or verification state here. |
| `PATCH /experts/{id}/verify/` | Staff/admin | `status` (`verified` or `rejected`), optional `badge_tier`, `rejection_reason` | Updated verification state; a rejection requires a reason. |

Only verified experts appear in public lists or profiles. Keep the profession
enum values synchronized with the app (for example, `doctor`, `nurse`,
`lawyer`, `financial_advisor`, and `other`).

### Articles and drafts

`GET /articles/` is public and returns only published articles. Accept
`category` as a category slug, `profession`, `search`, `order_by`, and `page`.
Support the app's sort values: `-published_at`, `-view_count`, `-save_count`,
`reading_time`, and `-reading_time`. Search title, summary, and body. Default
to newest published first and page size 20.

Article list objects, also used inside saved-article responses:

```json
{
  "id": 41,
  "slug": "example-article",
  "title": "Example article title",
  "summary": "A short summary of this example article.",
  "author_name": "Ari Example",
  "featured_image": null,
  "category_name": "Health",
  "category_slug": "health",
  "category_icon": "heart",
  "category_color": "#ff0000",
  "reading_time": 3,
  "view_count": 10,
  "save_count": 2,
  "published_at": "2026-10-16T11:00:00Z",
  "created_at": "2026-10-15T11:00:00Z"
}
```

| Method and path | Access | Request | Response/behavior |
|---|---|---|---|
| `GET /articles/` | Public | Query parameters above | Paginated `{count, next, previous, results}` of article-list objects. |
| `GET /articles/{slug}/` | Public | — | Article detail; increment `view_count`. Include list fields plus `body`, `status`, `updated_at`, `is_author`, nested `category` (`id`, `slug`, `name`, `content_type`, `icon_name`, `color_code`) and nested `author`. Include `author.expert_profile.profession` because the detail screen reads it. |
| `POST /articles/drafts/` | Verified provider | `title`, `summary`, `body`, `category_id` (accept `category` as a legacy alias), optional `featured_image` | `201`: `{status: "success", draft}`. Draft fields may be incomplete. |
| `POST /articles/drafts/{id}/save/` | Draft owner/provider | Any subset of draft fields | `{status: "success", draft}`. Update `version`, `updated_at`, `last_auto_save`, and `is_auto_saved` atomically. |
| `POST /articles/drafts/{id}/publish/` | Draft owner/provider | — | Validate title, body, and category; create or update the linked article as published; return `{status, message, article}`. Delete the consumed draft after successful publication, matching current behavior. |
| `GET /articles/me/drafts/` | Verified provider | `page` | Paginated article-list objects for the provider's draft articles. |
| `GET /articles/drafts/` | Verified provider | `page` | Paginated draft summaries (`id`, `title`, `progress`, `article_id`, `updated_at`, `last_auto_save`). |
| `GET /articles/drafts/{id}/` | Draft owner/provider | — | Draft detail (`id`, `title`, `summary`, `body`, `category_id`, `featured_image`, `progress`, `version`, `updated_at`). |
| `DELETE /articles/drafts/{id}/` | Draft owner/provider | — | Delete only the caller's draft; return the documented success response or `204`. |
| `DELETE /articles/{id}/` | Article owner | — | Delete only the caller's unpublished draft article; published articles cannot be deleted via this route. |
| `POST /articles/{id}/publish/` | Article owner/provider | — | Optional compatibility route for publishing an existing draft article; return `{status, message, article}`. |

Paginated responses use the Django REST Framework-compatible shape:
`{count, next, previous, results}`. `next`/`previous` are URLs or `null`; the
mobile app uses `results` and tests whether `next !== null`.

### Categories

| Method and path | Access | Response |
|---|---|---|
| `GET /categories/` | Public | Active category array or paginated response; the app normalizes either to an array. Each object has `id`, `slug`, `name`, `description`, `content_type`, `content_type_display`, `icon_name`, `color_code`, and `order`. |
| `GET /categories/{slug}/` | Public | Same fields plus `template` (JSON or `null`). |

### Engagements

| Method and path | Access | Request/query | Response |
|---|---|---|---|
| `POST /engagements/saved/save/` | User | `{article_id}` | `201`: `{status, message, saved_article}`; repeated save is idempotent and returns an informational status. Only published articles may be saved. |
| `POST /engagements/saved/unsave/` | User | `{article_id}` | `{status, message}`; repeated unsave is idempotent. |
| `GET /engagements/saved/` | User | `page` | Paginated `SavedArticle` objects: `{id, article: <article-list object>, saved_at}`. |
| `GET /engagements/saved/count/` | User | — | `{status: "success", saved_count}`. |
| `GET /engagements/saved/check/` | User | `article_id` | `{status: "success", is_saved}`. |
| `POST /engagements/history/record/` | User | `{article_id}` | `201`: `{status, message}`; create one row per user/article and refresh `read_at` on subsequent reads. |
| `GET /engagements/history/` | User | `page` | Paginated records `{id, article: <article-list object>, read_at}`. |
| `GET /engagements/stats/` and `GET /engagements/stats/{article_id}/` | Public | — | Optional compatibility endpoints exposing stats only for published articles. |

Keep save/unsave and history operations transactional. Derive counters from
successful unique record changes so retries cannot double-count. For article
statistics, keep `total_saves`, `total_reads`, `unique_readers`, and
`engagement_score` synchronized in the same transaction (or make them
explicitly rebuildable from the source tables).

## Shared response and validation rules

- Keep successful response envelopes and field names shown above. Validation
  failures should be `400` with `{status: "error", errors: {field: [messages]}}`;
  authentication failures should be `401`, permission failures `403`, and
  missing resources `404`. Keep a top-level `message` where the app currently
  reads one.
- Keep JSON dates timezone-aware ISO-8601 strings in UTC.
- Require ownership checks on drafts and articles; never accept a user ID from
  the request body as the authenticated owner.
- Restrict public article and expert results to published and verified
  records, respectively.
- Use an allowlist for sort fields and bound pagination inputs.
- Return article detail fields as well as list fields because screens can
  navigate to detail with a list item and then refetch by slug.

## Authentication and data migration cautions

The current app expects bearer JWTs, 1-hour access tokens, 7-day refresh
tokens, and a refresh response whose `access` value is top-level. To avoid
forcing an app update, retain those lifetimes and the refresh endpoint shape.
If tokens must remain interoperable during a rolling deployment, preserve
the current SimpleJWT signing algorithm/secret and claims (`user_id`,
`token_type`); never expose secrets in this document, code, or logs.

Existing passwords are Django password hashes. Do not replace those hashes
with a different scheme in a migration without an account recovery plan.
Either implement verification for the currently configured Django hash
format and rehash on successful login, or require password resets. Verify the
production database's actual hashers before selecting the transition.

Before connecting FastAPI to the Django database, map the existing tables and
inspect actual column names, constraints, migrations, and data. Do not run
Alembic `create_all` against the live Django database or assume that matching
ORM class names make schemas compatible. Use a reviewed Alembic baseline and
explicit migrations, preserve existing primary keys and foreign-key
relationships, and rehearse rollback on a copy of production data.

## Frontend/backend compatibility findings

1. The app calls `PUT /experts/me/`; the current Django action is named
   `update_profile`, which normally registers a different action URL. FastAPI
   should implement the app's `/experts/me/` route directly.
2. Draft requests currently send both `category` and `category_id`; draft
   creation currently persists only `category_id` and omits
   `featured_image`. Make `category_id` canonical, accept `category` as an
   alias during transition, and persist `featured_image`.
3. The detail screen reads `article.author.expert_profile.profession`, but
   Django's current article detail user serializer does not include
   `expert_profile`. Include that nested field (or update the screen to fetch
   expert data) rather than returning a payload that renders an incorrect
   generic title.
4. The public expert profile screen renders `expert.articles`, but the current
   public expert serializer only returns `article_count`. Include the
   published article list in that response, or change the app to fetch it
   separately.
5. Advanced search has a profession selector but its current API helper does
   not send `profession`; it also passes `reading_time` sort values that the
   current Django endpoint does not accept. FastAPI should support these
   sort values; wire the profession query through the mobile helper if the
   selector is expected to filter results.

## Suggested cutover sequence

1. Freeze and document the existing API contract; back up the PostgreSQL
   database and record row counts and maximum IDs per table.
2. Implement schemas, data access, authentication, and API routes in FastAPI
   against a local/staging database. Preserve response envelopes and run
   contract tests for every route listed above.
3. Validate password-hash login and JWT refresh behavior with existing user
   records. Validate uniqueness, ownership, publication, and counter behavior.
4. Point a test build of the mobile app at FastAPI and test registration,
   login/refresh, feed/search, expert apply/profile, draft autosave/publish,
   saved articles, and read history.
5. Deploy FastAPI behind the same `/api` base URL, retain Django data and
   rollback capability until production checks pass, then retire Django
   services and dependencies in a separate change.
