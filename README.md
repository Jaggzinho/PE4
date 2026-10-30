# PE3 QC local web application

PE3 runs locally as one FastAPI process serving the built React application and
owning the DuckDB file. Production binds only to `127.0.0.1` and uses one
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
before restarting if you want the saved path to win. A missing configured file
stops startup rather than creating a blank database.

Optional arguments:

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
