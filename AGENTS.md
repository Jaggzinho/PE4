# AGENTS.md

## Project Mission

PE3 is a local-only Quality Control web application.

The target architecture is:

- Backend: Python, FastAPI, Pydantic, and a Service/Repository architecture.
- Frontend: TypeScript, React, and Vite.
- Database: one local DuckDB file managed by the FastAPI process.
- Production UI: the frontend build is served by FastAPI from `dist/`.
- Runtime: one Windows workstation or a trusted local network machine. This is not a public or cloud-hosted service.

Preserve its calculations, permissions, data import behavior, terminology, and workflows unless a change is explicitly requested.

## Repository Map

- `pe3_qc_app/`: shared domain, database, import, authentication, and Outlook integration code used by the web backend.
- `pe3_qc_app/db/`: DuckDB migrations and existing query/repository code.
- `pe3_qc_app/services/`: reusable domain logic. Prefer extracting logic here before exposing it through HTTP.
- `web/`: current React/Vite implementation. This is the frontend migration base.
- `tests/`: backend, repository, and migration tests.
- `qc.duckdb`: local application data. Treat it as user data, not as a disposable test fixture.

The desired end-state is:

```text
backend/
  app/
    main.py
    config.py
    api/
      deps.py
      routers/
        auth.py
        materials.py
        lots.py
        sinottico.py
        charts.py
        ratings.py
        imports.py
        settings.py
        jobs.py
    core/
      security.py
      permissions.py
      errors.py
    db/
      manager.py
      migrations/
      repositories/
    models/
      domain.py
    schemas/
    services/
      auth.py
      lots.py
      sinottico.py
      charts.py
      ratings.py
      imports.py
      notifications.py
    jobs/
      manager.py
  tests/
frontend/
  src/
    api/
    components/
    features/
    hooks/
    layouts/
    pages/
    routes/
    schemas/
    styles/
    types/
    main.tsx
dist/
```

Do not perform a directory-wide rewrite merely to match this tree. Move code incrementally, keeping the application runnable and tests passing after each change.

## Local-Only Constraints

- Bind production and development services to `127.0.0.1` by default, never `0.0.0.0`.
- Do not add Cloudflare Tunnel, public ingress, cloud storage, telemetry, or externally hosted runtime dependencies.
- Do not use CDN-hosted JavaScript, fonts, or styles. Production assets must be bundled locally.
- Keep CORS disabled in the single-origin production build. In development, allow only the explicit Vite origin such as `http://127.0.0.1:5173`.
- Store configuration and data in local files. Secrets must come from environment variables or a local ignored configuration file, never source control.
- Do not assume internet access at runtime. Package all Python and frontend dependencies during installation/build.
- Keep setup and administration endpoints inaccessible after initial setup where practical. Never expose setup tokens in UI output or logs.
- Opening the browser may be automated, but the application must remain usable by navigating to `http://127.0.0.1:<port>` manually.
- If LAN access is ever requested, treat it as a separate security and deployment change requiring explicit authorization.

## Architecture Rules

### Request Flow

Use this dependency direction:

```text
React UI -> FastAPI router -> service -> repository -> DuckDB
```

- Routers validate transport data, enforce authentication/permissions, call a service, and translate known errors to HTTP responses.
- Services own workflows, calculations, authorization-sensitive decisions, and transaction boundaries.
- Repositories own SQL and database row mapping. They do not import FastAPI or frontend concepts.
- Pydantic schemas define API input and output contracts. Do not return raw DuckDB rows.
- React components do not contain SQL-derived business calculations that belong in Python.

### Extracting PySide Logic

When migrating a page, first inspect its widgets, signal handlers, workers, repositories, and tests. Extract behavior before replacing the UI.

Known migration boundaries:

| PySide area | Backend owner | Web interaction |
| --- | --- | --- |
| `LoginWindow` | `AuthService`, user/role repositories | REST login and current-session endpoints |
| `MainWindow` navigation and material selection | frontend router and URL state | React Router |
| `MainWindow.closeEvent` notifications | `NotificationService` | explicit REST action or local shutdown hook |
| `SinotticoPage` | `SinotticoService`, `SampleQueueService` | REST CRUD; job events only when useful |
| `LottiPage` | `LotsService` | REST CRUD with atomic measurement updates |
| `ChartsPage` | `ChartService` | REST query; chart rendering in React |
| `RatingsPage` | `RatingService` | REST query; chart/table rendering in React |
| `CalendarPage` | test/rating query services | REST month query |
| `ImportPage` | `ImportService` and job manager | multipart REST upload plus job status/progress |
| Settings and master data pages | focused services/repositories | permission-protected REST CRUD |

Do not mechanically reproduce Qt signals. Use:

- React Query invalidation or a fresh GET for ordinary `data_changed` events.
- URL/search parameters for selected material, date range, and view state.
- REST responses for request-scoped success and failure.
- WebSocket or Server-Sent Events only for meaningful long-running progress or cross-window updates.

### Long-Running Work

- Ordinary DuckDB reads, chart calculations, and rating queries may run in FastAPI's thread pool when they are short and bounded.
- Imports and other multi-step operations should create a local job record with status, progress, result, and error fields.
- `BackgroundTasks` is acceptable only for short, non-critical work that can be lost if the process exits.
- Prefer a dedicated in-process worker and serialized write queue for durable local jobs.
- Do not add Celery or Redis for this local-only application unless measurements show that an external worker is genuinely required.
- Support cancellation only where the underlying operation can be interrupted safely.

## DuckDB Rules

DuckDB is embedded and permits one writing process. Design around that constraint.

- Run one FastAPI/Uvicorn worker. Never configure multiple worker processes against the same database file.
- The FastAPI process is the sole owner of production database access. Do not let the PySide app and web backend write the same file concurrently.
- Serialize all writes through one application-level lock or dedicated write executor.
- Keep transactions short and explicit. Group related lot, measurement, queue, and import changes atomically.
- Reads may use short-lived connections, but connection lifecycle must be controlled by the database manager.
- Never keep a transaction open while waiting for browser input, file selection, email UI, or network activity.
- Apply schema changes through numbered, repeatable migrations. Never edit a user's database manually as part of normal startup.
- Parameterize all SQL values. Dynamic identifiers must come from a strict allowlist.
- Put SQL in repository modules and preserve the current query semantics with tests before optimizing it.
- Tests must use temporary DuckDB files. Never point automated tests at `qc.duckdb`.
- Before changing migrations or import behavior, make a backup-copy strategy explicit and test migration against a copied database.

If concurrent remote users, multiple backend processes, or high write throughput become requirements, propose migration to PostgreSQL instead of trying to make DuckDB act as a client-server database.

## API Conventions

- Keep application endpoints under `/api`.
- Use nouns and standard methods: GET for queries, POST for creation/actions, PUT/PATCH for updates, and DELETE for deletion.
- Return consistent JSON errors with a stable machine-readable code and a human-readable message.
- Enforce RBAC in backend dependencies/services. Hiding a frontend button is not authorization.
- Preserve the current first-run admin flow, but make it local-only, token-protected, and unavailable once a user exists.
- Validate uploaded file type, size, and workbook structure before import.
- Keep OpenAPI usable as the primary manual API verification surface.
- Add pagination or bounded date ranges to endpoints that can return unbounded test history.

## Frontend Conventions

- Use React with strict TypeScript. Avoid `any`; model API contracts explicitly.
- Use React Router for pages and URL-addressable filters.
- Prefer TanStack Query for server state and cache invalidation.
- Prefer TanStack Table for QC grids. Introduce AG Grid only if grouping, pivoting, or spreadsheet editing requirements justify its weight and license implications.
- Use React Hook Form with Zod for reactive forms. Keep matching constraints in Pydantic because the backend remains authoritative.
- Continue with Plotly while migrating existing chart behavior. Consider ECharts only as a deliberate replacement, not alongside a second chart system without need.
- Use Tailwind CSS or small shared layout primitives for new UI work; preserve a restrained operational-tool visual style.
- Use Lucide icons for common actions and accessible text/tooltips where needed.
- Every async view needs loading, empty, error, and permission-denied states.
- Preserve keyboard usability, visible focus, labels, and sufficient contrast.
- Do not reproduce desktop modal-heavy interaction when an inline form or dedicated route is clearer.

## Static Build and Runtime

Development uses two loopback services:

```text
Vite:    http://127.0.0.1:5173
FastAPI: http://127.0.0.1:8000
```

Vite proxies `/api` and any future `/ws` path to FastAPI. Production uses one origin: build the frontend into repository-level `dist/`, expose `/api` before static routes, serve hashed assets directly, and return `dist/index.html` only for non-API client routes.

Never let the SPA fallback turn an unknown `/api/...` request into an HTML `200` response.

Production startup should be equivalent to:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```


## Outlook and Notifications

The legacy application uses local Outlook COM automation. Keep this behind `NotificationService` so transport concerns do not leak into QC workflows.

- Run COM work off the request thread and initialize COM inside the worker thread.
- Prefer creating a reviewable `.eml` draft or opening a local Outlook draft over silently sending mail.
- Treat recipients, subject, body, and attachments as validated domain data.
- A missing Outlook installation must produce a clear recoverable error and must not roll back completed QC database work unless both actions are explicitly one transaction in the workflow.
- Do not add a cloud email provider without an explicit requirement.

## Testing and Verification

For backend changes:

```powershell
python -m pytest
```

For frontend changes:

```powershell
Set-Location web
npm run build
```

Add or update tests for:

- service-level business behavior;
- repository queries and transaction rollback;
- authentication and every permission-protected mutation;
- migration idempotency and upgrades from a copied prior schema;
- import validation, success, rollback, and duplicate handling;
- API response schemas and error codes;
- SPA fallback behavior, especially unknown `/api` routes;
- DuckDB write serialization when a change touches concurrent work.

For user-facing flows, verify the built app through `127.0.0.1`, not only through isolated unit tests.

## Safe Change Policy

- Inspect `git status` before editing. The repository may contain user changes, generated builds, and a modified local database.
- Do not revert or overwrite changes you did not make.
- Do not delete, replace, migrate, or commit `qc.duckdb` unless the task explicitly requires it.
- Do not commit `node_modules`, Python caches, logs, local secrets, uploaded workbooks, generated `.eml` files, or database backups.
- Keep generated `dist/` changes separate from source changes when practical.
- Favor focused modules and incremental extraction. Split a module when it mixes transport, business rules, SQL, and serialization; do not chase an arbitrary line-count rule.
- Preserve compatibility with current data and tests while a feature is being migrated.

## Migration Order

1. Extract and test Pydantic contracts, services, repositories, and transaction boundaries from PySide handlers.
2. Split the FastAPI API into domain routers and cover endpoints through OpenAPI and automated tests.
3. Migrate React pages feature by feature, preserving permissions and QC behavior.
4. Add local job progress only where synchronous requests are insufficient.
5. Build the frontend into `dist/`, serve it from FastAPI, and package a one-command local startup.
6. Retire a PySide page only after its web replacement passes behavioral and data-compatibility checks.

## Definition of Done

A migrated feature is complete when:

- no new business logic is embedded in a React component or FastAPI router;
- SQL is isolated in a repository and writes are serialized;
- Pydantic and TypeScript contracts agree;
- backend authorization is tested;
- loading, empty, validation, and failure states are usable;
- relevant backend tests and the frontend production build pass;
- the workflow works from the locally served application without internet access;
- existing user data remains compatible and untouched outside explicit migrations.
