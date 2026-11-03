# Four isolated QC environments

Status: implemented in source, with temporary-database and built-app verification.
Production database cutover is a separate local startup step; development checks
do not open the user's existing QC database.

## Agreed scope

Keep one locally hosted application and one shared implementation of QC workflows,
calculations, permissions, and workbook import logic/template. Provide four separate
QC DuckDB files, selected at login. The three new environments start with empty QC
data and the same schema/import template (confirmed by the user).

| Stable ID | Login display | QC database |
| --- | --- | --- |
| `tcm_ro` | 🇷🇴 TCM Romania | Keep the currently configured database in place |
| `wam_ro` | 🇷🇴 WAM Romania | `data/environments/wam_ro/qc.duckdb` |
| `tcm_it` | 🇮🇹 TCM Italia | `data/environments/tcm_it/qc.duckdb` |
| `wam_wuxi` | 🇨🇳 WAM WuXi | `data/environments/wam_wuxi/qc.duckdb` |

Paths for new files are proposed defaults resolved relative to the application
data directory. Existing TCM Romania data must never be replaced or emptied.
New environments contain required schema/system defaults, but no copied materials,
components, Sinottico entries, lots, measurements, queues, or import history.

For this release, all active users can log in to all four environments with the
same account, password, role, and permissions. Account administration is global.
Environment-specific user membership is a future extension.

## Findings from the current implementation

- `backend/app/config.py`, `main.py`, and `api/deps.py` configure one database,
  one subsidiary ID, and one import job manager for the whole process.
- `pe3_qc_app/core/subsidiaries.py` already defines these four stable IDs and flag
  keys. Reuse it, reorder the display list as requested, and correct Wuxi to WuXi.
- JWTs currently contain identity/permissions but no environment.
- Authentication and user/role administration currently use the QC database.
- Tests, sample requests, and sample queues have foreign keys to local `users`.
  Shared authentication therefore needs an explicit identity-reference design.
- `JobManager` already owns a fixed database and a single worker. This is a useful
  isolation boundary when instantiated separately for each environment.
- Several routers read `state.subsidiary_id` directly; replacing only the database
  dependency would leave material visibility and other behavior incorrectly scoped.
- `material_visibility.py` has existing subsidiary defaults. Preserve these rules;
  empty visibility lists currently fall back to active Sinottico materials.
- Database selection in Settings currently changes the next process-wide startup
  path. That behavior must become environment-specific.
- The frontend stores the bearer token in localStorage, shared across tabs. That
  must be addressed to support simultaneous environments in separate tabs.

## Proposed design

### Environment registry and database ownership

Introduce a validated local registry mapping the four allowlisted IDs to labels,
flag keys, subsidiary IDs, and QC paths. Keep filesystem paths server-side.
Reject duplicate resolved paths (including aliases to the same file), unknown IDs,
and invalid configuration. Never turn an arbitrary client value into a path.
Do not use the current subsidiary normalizer's fallback for API environment IDs:
an unknown selection must fail rather than silently access TCM Romania.

Keep one FastAPI process, one Uvicorn worker, the existing loopback binding, and
one frontend build. Create exactly one DbManager and one JobManager per QC file.
All writes to each file use its existing application-level lock. Separate files
can progress independently; no extra backend processes are needed.

Resolve an immutable environment context from the authenticated session for every
QC request. Route reads, transactional writes, serialized mutations, subsidiary
visibility, settings, notifications, exports, and job access through that context.
Never mutate a global active database when somebody logs in.

### Shared accounts

Recommended target: one additional local `data/auth.duckdb` as the authoritative
identity store for users, password hashes, roles, permissions, and account status.
This is shared infrastructure, separate from the four QC databases. Use separate
identity dependencies for login, setup, and user/role administration.

Transfer existing identities from TCM Romania without changing user/role IDs or
password hashes, so existing passwords and historical ownership remain valid.
The first-admin flow checks only this shared store and remains disabled once it
contains users; an empty QC database must never reopen setup.

Preserve local foreign-key integrity with non-authenticating identity projections
in each QC database. Projections contain stable identity IDs and the metadata
needed by existing QC references, not a second authoritative login/password store.
The implementation reuses the existing schema without rebuilding QC tables:
new projections are inactive users assigned to a non-privileged projection role,
with random, unusable credential bytes in the required password columns. Existing
TCM identity rows remain unchanged. A separate numbered schema initializes the
shared identity database transactionally. Foreign keys remain intact.

Create/update a user's local projection before a QC write referencing that user.
Use retryable, idempotent projection updates; shared account changes and QC writes
are separate transactions, with no promise of atomic commits across DuckDB files.
If a projection cannot be prepared, fail the dependent QC write cleanly. Preserve
historical identities when accounts are deactivated or deletion is restricted by
references. Password changes, account activation, and roles are read from the
shared authority, never from local projections. Check current account status and
permissions during authenticated requests so global changes take effect.

Keep shared-auth access behind a service boundary to allow per-environment account
access rules later without changing QC repositories.

### API and session contract

- Add `GET /api/environments`, available before login, returning only public IDs,
  labels, flag keys, and availability. Do not disclose database paths or secrets.
- Accept `environment_id` alongside username/password in `POST /api/auth/login`.
  The UI always sends it; existing API clients may omit it to select TCM Romania.
- Validate availability, authenticate against shared accounts, then issue a JWT
  containing the validated environment ID.
- Return the selected environment in `/api/auth/me` and matching TypeScript types.
- Reject tokens without a valid environment claim after cutover; users log in
  again rather than inheriting an ambiguous database context.
- Resolve every protected QC endpoint and job lookup from that claim. Headers,
  query parameters, and request bodies cannot override it.
- Use stable JSON error codes for invalid/unavailable environments and sessions.
  An unavailable environment must never fall back to another database.

### Login and application UI

Add a labelled, keyboard-accessible dropdown above the login credentials, ordered
TCM Romania, WAM Romania, TCM Italia, WAM WuXi. Default to TCM Romania initially;
optionally remember the last selection in that tab.

Use bundled local SVG flag assets for Romania, Italy, and China so the flag icons
render reliably on Windows and offline. The table above uses emoji only to show
the requested appearance. Include readable environment names with every flag.

Show the selected environment persistently in the signed-in application and on
the import screen. Switching environments uses logout and login for this release.
Use tab-scoped sessionStorage for the bearer token so separate tabs can remain
signed into different environments. Remove the legacy localStorage token at
cutover. Namespace saved filters/view state by environment, clear in-memory server
data on logout, and discard pending responses from the previous session. Any
query cache keys must include environment identity.

Provide loading, unavailable, empty, and error states for environment discovery.
Disable login when no valid environment is selected or discovery has failed.

### Imports and environment-local settings

Reuse the existing upload validation and `import_workbook` implementation for all
four environments, including the synchronous compatibility endpoint. Keep workbook
layout, parsing, validation, duplicate handling, and transaction behavior unchanged.
The environment is chosen by the session, not inferred from workbook content.

Capture the environment's fixed manager when accepting an import. Its job record,
execution, result, recovery, and history remain in that QC database, even if the
user logs out or opens another environment. Admin job visibility remains scoped
to the selected environment. Shut down every worker cleanly.

Keep QC master data, chart/rating settings, material visibility, notification
settings, and sample queues local to each environment. Existing TCM Romania
settings remain intact. New environments receive existing supported defaults,
not copied TCM settings or invented regional changes.

Adapt the database Settings page and startup scripts to the registry. Path changes
apply to the named environment after restart, preserve the legacy TCM path during
configuration upgrade, and cannot alias another QC file or the auth store.
Label user/role administration as shared across all environments.

## Incremental delivery

1. Add registry/configuration contracts and tests, preserving current single-file
   startup until cutover. Audit all direct AppState/database/subsidiary accesses.
2. Implement shared identity repositories/services and projection migrations.
   Exercise identity extraction, foreign keys, and rollback on disposable copies.
3. Add environment-bound sessions and request dependencies. Scope every QC router,
   notification/export path, Settings path action, and import job manager.
4. Add the login selector, local flag assets, signed-in environment display,
   tab-isolated authentication, and environment-scoped frontend state.
5. Build and verify all four environments locally using temporary databases.
6. Perform a backed-up, explicit production cutover and update local run docs.

## Data safety and cutover

No production data is changed while planning or testing. Before implementation
changes migrations/import routing, define and exercise the backup strategy:
stop application writers and workers, close DuckDB connections, and create a
verified offline backup of the configured TCM database and local configuration
outside source control. Never copy a live database file while writes are active.

Rehearse the entire upgrade on a copy. Check schema versions, user IDs, credential
hash preservation, row counts, historical ownership, and representative QC results.
Create the three new QC files from migrations and defaults, not by cloning and
deleting production rows. Provision auth and registry configuration in staging,
validate them, then publish the new configuration only after successful preparation.
Provisioning must be repeatable and must never overwrite an existing QC file.

At cutover, keep the original TCM path, migrate only as required, invalidate old
sessions, and verify each environment. If preparation or verification fails, stop
the new process and restore the matched pre-cutover database/configuration and
application version before resuming work. Do not restore an old backup over new
post-cutover QC work without explicitly reconciling that work.

## Acceptance checks

- All four exact labels/flags display offline; the same credentials and role work
  in each, and global account administration affects all four.
- The three new QC environments are empty except required defaults/projections.
- TCM Romania retains existing QC data, settings, ownership, and calculations.
- Importing the same fixture through each environment uses identical behavior and
  changes only the selected database. Verify duplicate handling and rollback too.
- Overlapping row IDs cannot reveal or modify another environment's records.
  Exercise reads, every mutation class, queues, settings, exports, and job IDs.
- Unknown/disabled environment IDs, missing claims, forged tokens, arbitrary paths,
  and attempted environment overrides fail with stable errors and no fallback.
- Permission-protected mutations are enforced in each environment; account
  deactivation and password/role changes use the shared authority.
- Simultaneous tabs preserve distinct environments; logout/login clears stale
  data, pending responses, URL-selected IDs, and remembered filters appropriately.
- Imports remain pinned to their original environment through logout, concurrent
  imports, restart recovery, and shutdown. Writes remain serialized per file.
- Migration/provisioning tests use temporary files and copied prior schemas;
  repeated runs preserve data and foreign keys. Setup cannot reopen per environment.
- Run `python -m pytest` and `npm run build` from `web`, then verify the built app
  through `127.0.0.1` with disposable data. Preserve unknown `/api` JSON errors,
  production single-origin behavior, and offline runtime operation.
