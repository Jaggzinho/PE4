# PE3 QC local web application

PE3 runs locally as one FastAPI process serving the built React application and
owning the local DuckDB files. Production binds only to `127.0.0.1` and uses one
Uvicorn worker.

## Build

Install frontend dependencies and build once:

```powershell
python -m pip install -r requirements-web.txt
.\build-web.cmd -Install
```

Subsequent builds can omit `-Install`:

```powershell
.\build-web.cmd
```

The frontend is written to the repository-level `dist/`. FastAPI discovers
that directory automatically; `PE3_STATIC_DIR` remains available as an
explicit override.

## Start

Start with the default local database at `data\pe3.duckdb`:

```powershell
.\run-web.cmd
```

Or point PE3 at an existing database:

```powershell
.\run-web.cmd -DbPath "C:\path\to\qc.duckdb"
```

The launcher generates and reuses a local JWT secret under the ignored `data/`
directory, opens `http://127.0.0.1:8000`, and fixes Uvicorn to one worker. For a
new database, it stores the first-run setup token in an ignored local file and
prints only that file's path.

An administrator can inspect the active database path and source in Settings →
Database and save an existing `.duckdb` file as the next-startup source. The
web-only setting is stored in ignored `data/web-config.json` (or at
`PE3_WEB_CONFIG_PATH` when explicitly set). Saving does not change the running
connection or copy data; restart the web server to apply it. `-DbPath` and
`PE3_DB_PATH` take precedence over this setting, so remove either override
before restarting if you want the saved path to win. This override applies to
TCM Romania. A missing configured TCM file stops startup rather than creating a
blank database; unavailable additional environments cannot be selected at login.

## QC environments and shared logins

Select an environment on the login page:

| Environment | Default QC database |
| --- | --- |
| 🇷🇴 TCM Romania | Existing launch/configured path, unchanged |
| 🇷🇴 WAM Romania | `data/environments/wam_ro/qc.duckdb` |
| 🇮🇹 TCM Italia | `data/environments/tcm_it/qc.duckdb` |
| 🇨🇳 WAM WuXi | `data/environments/wam_wuxi/qc.duckdb` |

All four use the same calculations, import implementation, and workbook template.
The three new environments are created with empty QC data and system defaults.
Materials, results, queues, import jobs, and QC settings are independent. The active
environment appears in the sidebar and on the import screen. Log out to choose a
different environment. Separate tabs can stay signed into different environments.

Users, passwords, roles, and permissions are shared. On first startup with this
version, existing TCM accounts are copied transactionally into `data/auth.duckdb`,
preserving their IDs and password hashes. Later account administration uses that
shared store; accounts are not reimported at subsequent startups. Account deletion
is refused when QC history in any environment references the user; deactivate the
account instead. New local QC identity references are inactive and have no usable
copied password. The existing TCM identity rows and historical ownership remain.

Before the first production startup, stop the previous application and all its
workers, then make an offline backup of its database and local configuration.
Never copy a DuckDB file while it is being written. Keep the old application version
with the backup. Development tests rehearse startup against disposable database
copies. After adoption, back up all four QC files, `auth.duckdb`, and local
configuration together while the server is stopped. Do not discard the shared
auth store: it is the authority for account changes made after adoption.

The launcher anchors the application data directory at repository/bundle `data/`.
`PE3_DATA_DIR` overrides it; `PE3_AUTH_DB_PATH` overrides the shared login-store
path. When starting the FastAPI factory directly, the default data directory is
the parent of `PE3_DB_PATH` unless saved local configuration specifies otherwise.
Set `PE3_DATA_DIR` explicitly for a stable custom location. Paths remain server-side.

Settings → Database saves the next-startup path for the signed-in environment.
It cannot select another environment's file or the shared login store. Saving also
preserves the data-directory/auth-store locations so moving TCM's QC file does not
move the other stores. Additional environment paths are stored in local
`web-config.json` as:

```json
{
  "environments": {
    "wam_ro": "C:/PE3/data/environments/wam_ro/qc.duckdb",
    "tcm_it": "C:/PE3/data/environments/tcm_it/qc.duckdb",
    "wam_wuxi": "C:/PE3/data/environments/wam_wuxi/qc.duckdb"
  }
}
```

Explicitly configured paths must already exist. Omit additional environment
entries to create their empty databases at the defaults. Keep TCM's existing
`db_path` setting at the top level. Every store must resolve to a distinct file.
The backend remains the sole owner of all database access; do not run the legacy
desktop application against these files concurrently.

Existing browser tokens are invalidated by this upgrade. Sign in again and select
an environment. API clients may continue to omit `environment_id` on login to use
TCM Romania; new clients should send an explicit selection. OpenAPI exposes
`GET /api/environments` and the environment-aware login/session schemas.

Optional launch arguments:

```powershell
.\run-web.cmd -Port 8010 -NoBrowser
```

## Run as a Windows service (optional)

The server can be wrapped in a Windows service with [NSSM](https://nssm.cc) so
it starts at boot (no login required) and restarts automatically after a
crash:

```powershell
nssm install PE3QC <python-exe> "-m backend.app.launcher --host 0.0.0.0 --port 8000 --no-browser"
nssm set PE3QC AppDirectory <repo-root>
nssm set PE3QC AppStdout <repo-root>\data\service-stdout.log
nssm set PE3QC AppStderr <repo-root>\data\service-stderr.log
nssm set PE3QC Start SERVICE_AUTO_START
nssm start PE3QC
```

Manage it like any Windows service: `Start-Service PE3QC`,
`Stop-Service PE3QC`, `Restart-Service PE3QC`. Remove the wrapper with
`nssm remove PE3QC confirm`. The service runs as LOCAL SYSTEM by default,
so the Outlook COM draft integration is unavailable while it runs this way
and reverts to its regular recoverable error. `--host 0.0.0.0` shares the
application over the trusted local network only.

## Development

Use `run-dev.cmd` for the two-process Vite/FastAPI development setup. Vite
proxies `/api` to `http://127.0.0.1:8000`.

Required backend environment variables when starting Uvicorn directly:

- `PE3_DB_PATH`: DuckDB path.
- `PE3_WEB_CONFIG_PATH`: optional local web config file path; useful for isolated tests or installations. When `PE3_DB_PATH` is absent, direct Uvicorn startup uses its configured database path.
- `PE3_JWT_SECRET`: JWT signing secret of at least 32 random characters.
- `PE3_STATIC_DIR`: optional built frontend override.
- `PE3_SETUP_TOKEN`: optional first-run administrator token.
- `PE3_DEV=1` and `PE3_CORS_ORIGINS=http://127.0.0.1:5173`: development only.

Direct production-equivalent startup:

```powershell
python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

## Validate a representative database safely

The validation utility hashes the source, copies it to a temporary directory,
applies startup migrations only to the copy, and smoke-tests authenticated web
workflows:

```powershell
python -m tools.validate_web_cutover C:\path\to\qc.duckdb
```

## Built-app browser regression

The Playwright suite builds the frontend, starts FastAPI on loopback, and uses
only generated databases under ignored `.e2e/`. It never opens or copies
`qc.duckdb`:

```powershell
Set-Location web
npm run test:e2e
```

The suite uses the locally installed Microsoft Edge browser and covers login,
permission boundaries, workbook import/history, URL-addressable QC navigation,
the Outlook test-draft `.eml` fallback, and next-startup database selection.
Failure traces, screenshots, and videos are written to ignored directories in
`web/`.
