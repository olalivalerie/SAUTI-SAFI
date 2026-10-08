# SAUTI SAFI — Phase 3 Authentication and Dashboard

This package is the Phase 3 baseline. It provides a working PostgreSQL backed account system and protected dashboard foundation before Phase 4 data collection and analysis are added.

## Included

- Public landing page
- Pricing page
- Account registration
- Secure password hashing with Argon2
- JWT sign in and protected API requests
- Current user endpoint
- Sign out
- Forgot password flow
- One time password reset tokens valid for 30 minutes
- Local development reset links when SMTP is not configured
- PostgreSQL backed dashboard data
- Stored posts and alerts displayed in the dashboard
- CORS configuration for VS Code Live Server
- Safe startup handling for common Phase 2 to Phase 3 user table changes

## Local setup

1. Create the database in PostgreSQL.
2. Copy `.env.example` to `.env`.
3. Set `DATABASE_URL` and generate a strong `SECRET_KEY`.
4. Create or activate your virtual environment.
5. Install dependencies:

```bash
pip install -r backend/app/requirements.txt
```

6. Start the backend from the project root:

```bash
uvicorn backend.app.main:app --reload
```

7. Open `frontend/index.html` with VS Code Live Server.

Use:

- Frontend: `http://127.0.0.1:5500`
- Backend: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

Do not open the HTML files with `file://`.

## Authentication test

Test this sequence before Phase 4:

1. Create an account.
2. Register with the same email again and confirm it is rejected.
3. Sign in with the correct password.
4. Confirm the browser reaches the dashboard.
5. Refresh the dashboard and confirm the session remains active.
6. Sign out and confirm the dashboard redirects to sign in.
7. Try the dashboard while signed out and confirm access is denied.
8. Use Forgot password.
9. With SMTP disabled, copy the reset URL printed in the FastAPI terminal.
10. Set a new password.
11. Confirm the old password fails and the new password works.
12. Reuse the reset URL and confirm it is rejected.

## Dashboard

The dashboard is authenticated and reads `/dashboard`. It does not invent social media posts. It shows records stored in PostgreSQL and remains empty until a future authorized collector writes records to the `posts` and `alerts` tables.

## Security

Never commit `.env`, passwords, API keys, JWT secrets, `.git`, or `.venv`. The release ZIP intentionally excludes them.

JWTs are stored in browser local storage for this MVP. Before production deployment, move authentication to secure HTTP only cookies and add a formal migration system such as Alembic.

## Phase 4 boundary

Phase 4 should add authorized data collection, monitoring topics, deduplication, analysis, scoring, alert generation, and reporting. It should not replace the Phase 3 authentication flow.

## Existing database upgrade

If you already used a Phase 2 database, do not delete your users. Phase 3 now upgrades the existing PostgreSQL `users` table automatically when the API starts. It adds the missing `plan`, `is_active`, `is_superuser`, `created_at`, and `updated_at` columns and creates the password reset table.

If you need to repair the database manually, run `phase3_database_repair.sql` against the same database in `DATABASE_URL`.

For example:

```bash
psql "$DATABASE_URL" -f phase3_database_repair.sql
```

Then start the API from the extracted Phase 3 project directory:

```bash
uvicorn backend.app.main:app --reload
```

## Phase 4: real X ingestion and baseline analysis

Phase 4 adds topic based X recent search, persistent monitoring topics, database ingestion, a transparent rule based risk baseline, and automatic early warning alerts.

### X API configuration

Add this to `.env`:

```env
X_BEARER_TOKEN=YOUR_X_APP_BEARER_TOKEN
```

The collector uses `GET https://api.x.com/2/tweets/search/recent`. Recent Search covers the last seven days and supports up to 100 results per request. SAUTI SAFI intentionally starts with controlled polling so API usage can be measured before any background scheduler is enabled.

### Phase 4 flow

1. Sign in.
2. Add a monitoring topic and an X search query.
3. Click **Collect from X now**.
4. SAUTI SAFI stores new posts in PostgreSQL.
5. Each post receives baseline misinformation and hate speech risk indicators.
6. High priority records create early warning alerts.
7. The dashboard refreshes from stored backend data.

The Phase 4 scorer is a transparent baseline. A score is a risk indicator, not a factual finding that a post is misinformation or that a person is hateful. Model evaluation and a stronger classifier come after the ingestion pipeline is proven.
