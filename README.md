# JobsVsAI Phase 1

JobsVsAI is a career-intelligence MVP that keeps **AI Exposure** separate from **Replacement Risk**, explains the task-level drivers behind both, and connects each analysis to realistic next-career options.

## Architecture

- `frontend/` — Next.js App Router, TypeScript, server-rendered profession and ranking pages
- `backend/` — FastAPI API with async PostgreSQL access
- `worker/` — RQ background worker for imports and dependency-based recalculation
- `scoring/` — versionable Python scoring logic
- `ingestion/` — source-specific ingestion boundary
- `migrations/` — normalized PostgreSQL schema and demo seed
- `docker-compose.yml` — local portable stack (Next.js, FastAPI, PostgreSQL, Redis, worker)

The frontend calls FastAPI for PostgreSQL-backed occupation records. There are no fixture fallbacks. Full scores are precomputed and stored; public requests never run scoring calculations.

## Run the complete stack

1. Copy `.env.example` to `.env` and replace the example passwords.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000`. API docs are at `http://localhost:8000/api/docs`.

In local development the SQL migrations run automatically when PostgreSQL creates a fresh
data volume. That hook only ever fires on an empty volume, so it is **not** how schema
changes reach a database that already holds data — see *Database migrations* under
Deployment below.

## O*NET subset ingestion

The O*NET ingestion boundary is staged and score-neutral. See `ingestion/ONET_MAPPING.md` before expanding its scope. After downloading the official 30.3 CSV files into `ingestion/data/onet/30.3`, apply migration `005_onet_ingestion_layer.sql` and run:

```bash
docker compose run --rm backend python -m ingestion.onet_import import \
  --version 30.3 \
  --data-dir ingestion/data/onet/30.3 \
  --subset-file ingestion/subsets/representative_31.txt
```

Replaying the same command is idempotent. Validate the current canonical layer with `python -m ingestion.onet_import validate --version 30.3` inside the backend service.

## Tests and validation

```bash
cd frontend && npm run lint && npm run build
python -m pytest backend/tests
```

## Phase 1 routes

- `/`, `/jobs/[slug]`, `/rankings`
- `/career-finder`, `/career-finder/results`
- `/compare`, `/compare/[job-a]-vs-[job-b]`
- `/methodology`, `/about`
- `/admin`, `/admin/jobs`, `/admin/jobs/[slug]`, `/admin/scores`, `/admin/imports`, `/admin/system`

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in production. The admin routes are intentionally excluded from public navigation and protected by HTTP Basic authentication in production.

## Production deployment

Target: a single VPS (2 vCPU / 8 GB, Ubuntu 24.04) running the same Compose stack behind
Caddy. No orchestrator, no extra datastores.

```
internet → Caddy (:80/:443, Let's Encrypt)
             ├── jobsvsai.com, www → frontend:3000
             └── api.jobsvsai.com  → backend:8000
                                      ├── postgres:5432   internal only
                                      └── redis:6379      internal only
```

Caddy is the only service that publishes a port. PostgreSQL, Redis, the API and the
frontend are reachable solely on the Compose network.

### First deployment (new host, one time)

The database is restored **before** the public application is allowed to start. Migrations
create the schema and seed reference data; they do not contain the O*NET corpus, the
scores or the published occupations, so a site started against an empty database would
serve zero occupations on a live domain.

**1. Provision and secure the VPS**

```bash
ssh <user>@<vps>                      # key-based; password auth disabled
# install Docker Engine + compose plugin, then:
git clone <repo> /opt/jobsvsai && cd /opt/jobsvsai
cp .env.production.example .env && chmod 600 .env    # fill in real values
sudo ./scripts/firewall.sh                            # SSH + HTTP + HTTPS only
```

**2. Point DNS** — all three records must resolve to the VPS before the first run or
certificate issuance fails.

| Record | Type | Value |
|---|---|---|
| `jobsvsai.com` | A | VPS IPv4 |
| `www.jobsvsai.com` | A | VPS IPv4 |
| `api.jobsvsai.com` | A | VPS IPv4 |

**3. Transfer the database dump** from the machine that holds the live data:

```bash
# source machine
docker compose exec -T postgres pg_dump -U jobsvsai -d jobsvsai -Fc --compress=9 > jobsvsai.dump
sha256sum jobsvsai.dump > jobsvsai.dump.sha256
scp jobsvsai.dump jobsvsai.dump.sha256 <user>@<vps>:/var/backups/jobsvsai/
```

**4. Deploy** — one command performs the whole ordered sequence:

```bash
./scripts/deploy.sh --restore /var/backups/jobsvsai/jobsvsai.dump
```

which does, in order:

1. validates `.env` (refuses placeholder credentials, or `ENVIRONMENT` other than `production`)
2. builds images
3. starts **PostgreSQL and Redis only**
4. restores the dump into the empty database, after checksum and disk-space checks
5. baselines migration history, then applies anything newer
6. **verifies** 507 public occupations, 507 live scores, `JVS 1.0.3` active and
   `JVS 2.0.0-phase4b` inactive — and aborts, with only the datastores running, if any
   of that is wrong
7. starts backend, worker, frontend and Caddy
8. runs the full health check

Expected counts can be overridden for a source database that has legitimately moved on:
`EXPECT_PUBLIC=520 EXPECT_SCORES=520 ./scripts/deploy.sh --restore <dump>`.

To stand up an intentionally empty instance, pass `--allow-empty-database`; the model
checks still apply.

`NEXT_PUBLIC_SITE_URL` and `NEXT_PUBLIC_API_URL` are compiled into the browser bundle at
**image build time**. Changing them needs a rebuild, not a restart.

Deployment does not run the public-content pipeline and does not change the active scoring
model. Content run 2 and the public activation already happened; they are carried in the
dump, not re-executed.

### Routine updates (existing host)

Never use `deploy.sh` for a release — it is the first-run path. Releases go through
`update.sh`, which backs up first and can undo itself:

```bash
./scripts/update.sh --pull
```

### Routine operations

| Task | Command |
|---|---|
| Release a new version | `./scripts/update.sh --pull` |
| Roll back the last release | `./scripts/rollback.sh` |
| Check everything | `./scripts/healthcheck.sh` |
| Back up now | `./scripts/backup-db.sh` |
| Restore a backup | `./scripts/restore-db.sh <dump>` |
| Migration status | `./scripts/migrate.sh --status` |
| Logs | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail 100` |

`update.sh` backs up the database, records the running images, rebuilds, migrates,
restarts, and **rolls back automatically** if the health check fails afterwards.

### Database migrations

`scripts/migrate.sh` applies pending migrations to a live database and records them in
`schema_migrations`. Each file runs at most once, in order; a file that declares its own
`BEGIN`/`COMMIT` manages its own transaction, and one that does not is wrapped in a single
transaction. Editing a migration that has already been applied is detected by checksum and
refused — add a new migration instead.

Migrations are **forward-only**. Rolling code back does not reverse a migration, because
reversing DDL against live data loses information. If a release shipped a bad migration,
roll the code back and restore the pre-update backup.

On a database whose schema is already current but which has no migration history (one
built by the old initdb hook, or restored from a dump), baseline it once:

```bash
./scripts/migrate.sh --baseline    # records all migrations as applied, runs none
```

### Backups

`scripts/backup-db.sh` writes a compressed `pg_dump -Fc` archive to `BACKUP_DIR`, verifies
it is readable with `pg_restore --list`, writes a SHA-256 sidecar, and prunes archives
older than `BACKUP_RETENTION_DAYS` (default 14). The database is ~5 GB, so budget roughly
400–700 MB per archive.

```bash
sudo crontab -e
15 3 * * * cd /opt/jobsvsai && ./scripts/backup-db.sh >> /var/log/jobsvsai-backup.log 2>&1
```

Restore, which stops the app, takes a safety dump of what it is about to overwrite,
requires typing `RESTORE`, and verifies row counts afterwards:

```bash
./scripts/restore-db.sh /var/backups/jobsvsai/jobsvsai-20260821T031500Z.dump
```

### Operational invariants

`healthcheck.sh` fails, deliberately, if any of these stop being true:

- the active scoring model is `JVS 1.0.3` — `JVS 2.0.0-phase4b` is registered but inactive,
  and the legacy worker writes under whichever model is active
- at least one occupation is public and carries a live production score
- the data console is not reachable on the API hostname
