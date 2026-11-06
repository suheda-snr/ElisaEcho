# Elisa Echo

AI-powered system that **automatically discovers and preserves hidden operational knowledge** from
the conversations telecom network engineers already have. Built for the Elisa challenge at the
Since AI Hackathon.

> **Status: Phases 1–2 are done.** The app shell, Docker setup, PostgreSQL schema (Alembic),
> read-only API and synthetic demo conversations work. Automatic knowledge discovery (Gemini),
> search, troubleshooting and the knowledge graph are **not implemented yet**. See the
> [roadmap](docs/roadmap.md).

## The problem

Engineers share valuable troubleshooting knowledge in Slack, Microsoft Teams and email. One
engineer reports a failing service, another remembers that restarting just that service (not
rebooting the whole device) fixed it last time, and the first confirms it worked. Nobody writes
it down, so the next engineer with the same symptoms starts from scratch.

## What Elisa Echo does

Elisa Echo finds that knowledge **automatically**. Engineers never have to submit, document or
categorize anything.

1. Ingest messages from authorized communication channels.
2. Group messages into conversation threads.
3. Analyze threads to find operational knowledge, distinguishing **ordinary messages**,
   **unverified suggestions** and **confirmed resolutions**.
4. Extract structured knowledge with Google Gemini: symptoms, equipment, steps, outcome,
   applicability conditions and links to the source messages.
5. Link knowledge to incidents, equipment and other expert contributions.
6. Store embeddings in Tiger Data PostgreSQL with pgvector.
7. When an engineer meets a similar problem, retrieve the earlier solution **with its evidence**,
   optionally as an interactive troubleshooting decision tree.

The demo uses **synthetic conversations**. No real Slack, Teams or email accounts are connected.
Full design: [docs/architecture.md](docs/architecture.md).

### Application pages

| Route           | Page                                   | Purpose                                                              |
| --------------- | -------------------------------------- | -------------------------------------------------------------------- |
| `/`             | Dashboard                              | Discovered knowledge, recent processing activity, system status      |
| `/capture`      | Communication Sources / Live Discovery | Incoming conversations and the knowledge automatically found in them |
| `/search`       | Search                                 | Search automatically extracted operational knowledge                 |
| `/troubleshoot` | Troubleshoot                           | Evidence-backed interactive decision trees                           |
| `/graph`        | Knowledge Graph                        | Incidents, equipment, conversations and resolutions                  |

## Tech stack

| Layer    | Tools                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | React 19, Vite 8, TypeScript 6 (strict), Tailwind CSS 4, shadcn/ui, React Router 8, TanStack Query 5, Axios, Lucide, React Flow, Recharts |
| Backend  | Python 3.12, FastAPI, Uvicorn, Pydantic 2, pydantic-settings, SQLAlchemy 2 (async), psycopg 3, Alembic, pgvector, python-dotenv |
| Database | Tiger Data hosted PostgreSQL with the pgvector extension                                                                         |
| Testing  | pytest, pytest-asyncio, httpx                                                                                                    |
| Dev env  | Docker, Docker Compose, Node.js 24 LTS, npm                                                                                      |

## Project structure

```text
.
├── compose.yaml          # Runs frontend + backend for local development
├── docs/                 # architecture.md (discovery workflow) and roadmap.md (phases)
├── frontend/             # React + Vite single-page app
│   ├── src/
│   │   ├── components/   # layout/ (sidebar, header) and ui/ (shadcn/ui)
│   │   ├── pages/        # One file per route
│   │   ├── hooks/        # TanStack Query hooks
│   │   ├── services/     # api.ts – shared Axios client
│   │   ├── types/        # Shared TypeScript types
│   │   └── lib/          # Utilities and navigation config
│   └── Dockerfile
└── backend/              # FastAPI service
    ├── app/
    │   ├── main.py       # App factory, CORS, routers, database error handling
    │   ├── api/          # router.py, deps.py + routes/ (one module per resource)
    │   ├── schemas/      # Pydantic request/response models
    │   ├── services/     # Business logic and queries, called by routes
    │   ├── models/       # SQLAlchemy ORM models
    │   ├── db/           # Async engine/session, declarative base, URL handling
    │   ├── seed/         # Synthetic demo conversations (`python -m app.seed`)
    │   └── core/         # config.py – typed settings
    ├── alembic/          # Database migrations
    ├── tests/            # Unit tests + integration/ (isolated test database)
    ├── requirements.txt      # Runtime dependencies
    ├── requirements-dev.txt  # + test tooling (installed in the dev image)
    └── Dockerfile
```

## Quick start (Docker – recommended)

You only need **Git** and **Docker Desktop** (Windows/macOS) or **Docker Engine with the Compose
plugin** (Linux). You do not need Node.js or Python installed to run the app this way.

1. Install Docker:
   - **Windows:** install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
     with the WSL 2 backend, then start Docker Desktop and wait until it says it is running.
   - **macOS:** install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/)
     and start it.
   - **Linux:** install [Docker Engine](https://docs.docker.com/engine/install/) and the
     [Compose plugin](https://docs.docker.com/compose/install/linux/).
2. Clone the repository and open a terminal in the project root.
3. (Optional) create local env files. The defaults work without them:

   ```bash
   # macOS / Linux / Git Bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

   ```powershell
   # Windows PowerShell
   Copy-Item backend/.env.example backend/.env
   Copy-Item frontend/.env.example frontend/.env
   ```

4. Start everything:

   ```bash
   docker compose up --build
   ```

5. Open the app:

   | What               | URL                                |
   | ------------------ | ---------------------------------- |
   | Frontend           | http://localhost:5173              |
   | Backend API        | http://localhost:8000              |
   | API docs (Swagger) | http://localhost:8000/docs         |
   | Health check       | http://localhost:8000/api/health   |

Stop with `Ctrl+C`, then remove the containers:

```bash
docker compose down
```

Useful commands:

```bash
docker compose up --build -d     # start in the background
docker compose logs -f backend   # follow logs of one service
docker compose down -v           # stop AND delete the node_modules volume (see below)
```

### Hot reload

Source folders are mounted into the containers, so edits on your machine apply immediately:

- **Frontend:** Vite hot module replacement updates the browser without a full reload.
- **Backend:** Uvicorn restarts automatically when a `.py` file changes.

File-change events from Windows and macOS hosts do not always reach containers, so file
**polling is on by default**. On Linux you can turn it off to save CPU:

```bash
DOCKER_FILE_POLLING=false docker compose up
```

### When dependencies change

- **Backend (`requirements.txt`):** run `docker compose up --build`.
- **Frontend (`package.json` / `package-lock.json`):** the container keeps `node_modules` in a
  named Docker volume. Recreate it so the new packages are installed:

  ```bash
  docker compose down -v
  docker compose up --build
  ```

## How the frontend talks to the backend

The browser always calls **relative** URLs such as `/api/health`. The Vite dev server proxies
every `/api/*` request to the backend:

- Inside Docker the proxy target is `http://backend:8000` (set via `API_PROXY_TARGET` in
  `compose.yaml`). `backend` is a Docker network name, which your browser cannot resolve. That
  is why browser code never uses it directly.
- Running Vite outside Docker, the proxy defaults to `http://localhost:8000`.

The Axios client lives in `frontend/src/services/api.ts`; its base URL comes from
`VITE_API_BASE_URL` (default `/api`).

## Database (Tiger Data PostgreSQL + pgvector)

The backend uses a **hosted Tiger Data PostgreSQL** service. There is no database container in
`compose.yaml`. Schema overview: [docs/architecture.md](docs/architecture.md#4-database-schema).

### 1. Connect to Tiger Data

1. In the [Tiger Data console](https://console.cloud.timescale.com/), open your service and copy
   its connection string from **Connect**. It looks like
   `postgres://tsdbadmin:PASSWORD@HOST:PORT/tsdb?sslmode=require`.
2. Create `backend/.env` from the example (see Quick start) and set:

   ```env
   DATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST:PORT/tsdb?sslmode=require
   ```

   `postgres://` and `postgresql://` URLs are converted to the async psycopg 3 driver
   automatically. Keep `sslmode=require`.
3. Restart the backend so it picks up the file: `docker compose up -d --force-recreate backend`.

The URL is read only by the backend. It is never logged, never returned by the API and must
never go into `frontend/.env`.

### 2. Run migrations

Migrations are **not** run automatically on startup. Apply them explicitly:

```bash
docker compose exec backend alembic upgrade head     # create / update the schema
docker compose exec backend alembic current          # show the applied revision
docker compose exec backend alembic history          # list migrations
```

The initial migration runs `CREATE EXTENSION IF NOT EXISTS vector` and creates all tables,
constraints and indexes. It never drops existing tables.

After changing models, create a new migration and review it before committing:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

### 3. Load the synthetic demo conversations

```bash
docker compose exec backend python -m app.seed
```

- Loads 4 **synthetic** conversations (17 messages) into a "Synthetic NOC chat (demo)" source:
  a confirmed fix (Site 42), irrelevant chatter, an unresolved problem and a thread with several
  competing suggestions.
- Stores **messages only**. No knowledge is pre-extracted; Phase 3 discovers it automatically.
- **Idempotent and additive:** safe to run repeatedly, never deletes anything, only touches its
  own synthetic rows.
- Refuses to run unless `ENVIRONMENT` is `development` or `test`.

### 4. Verify

```bash
curl http://localhost:8000/api/health/db
# {"status":"ok","database":"connected","pgvector":true,"detail":null}
```

`/api/health` keeps working when the database is down; `/api/health/db` then returns
`503` with `database` set to `not_configured`, `misconfigured` or `unreachable`. Then browse
the data at http://localhost:8000/docs or:

```bash
curl "http://localhost:8000/api/threads?limit=10"
```

### API endpoints

| Method | Path                          | Description                                           |
| ------ | ----------------------------- | ----------------------------------------------------- |
| GET    | `/api/health`                 | API is up (no database access)                        |
| GET    | `/api/health/db`              | `SELECT 1` against PostgreSQL + pgvector check        |
| GET    | `/api/sources`                | List communication sources                            |
| POST   | `/api/sources`                | Register a source (**development/test only**)         |
| GET    | `/api/threads`                | List threads (`source_id`, `processing_status` filters) |
| GET    | `/api/threads/{id}`           | Thread with its source and message count              |
| GET    | `/api/threads/{id}/messages`  | Messages in original order                            |
| GET    | `/api/knowledge`              | List knowledge items (`resolution_status`, `approval_status` filters) |
| GET    | `/api/knowledge/{id}`         | Knowledge item with evidence messages, equipment, incidents |

List endpoints are paginated with `limit` (1–100, default 50) and `offset`, and return
`{items, total, limit, offset}`. There is deliberately **no public endpoint that accepts
messages**: ingestion happens inside the backend (seed script now, simulated feed in Phase 3).

## Backend tests

Unit tests need no database. They force `DATABASE_URL` empty, so they never touch Tiger Data even
if `backend/.env` is configured:

```bash
docker compose exec backend pytest
```

Integration tests need an **isolated, disposable** PostgreSQL database. They rebuild its schema,
so they refuse to run unless the database name contains `test`. **Never point them at the shared
Tiger Data database.** The simplest option is a throwaway local container (test-only, not part of
`compose.yaml`):

```bash
# Start (once). It joins the Compose network so the backend container can reach it.
docker run -d --name elisa-echo-testdb --network elisa-echo_default \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=elisa_echo_test \
  pgvector/pgvector:0.8.7-pg17-trixie

# Run everything
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@elisa-echo-testdb:5432/elisa_echo_test backend pytest

# Remove when done
docker rm -f elisa-echo-testdb
```

In PowerShell, put the `docker run` command on one line (or replace each trailing `\` with a
backtick). Without `TEST_DATABASE_URL` the integration tests are skipped.

## Environment variables

| File                    | Variable            | Default                 | Notes                                 |
| ----------------------- | ------------------- | ----------------------- | ------------------------------------- |
| `frontend/.env`         | `VITE_API_BASE_URL` | `/api`                  | Public. Bundled into browser code.    |
| `backend/.env`          | `APP_NAME`          | `Elisa Echo API`        |                                       |
| `backend/.env`          | `ENVIRONMENT`       | `development`           |                                       |
| `backend/.env`          | `CORS_ORIGINS`      | `http://localhost:5173` | Comma-separated list                  |
| `backend/.env`          | `DATABASE_URL`      | –                       | Tiger Data connection string. Secret. |
| `backend/.env`          | `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | `5` / `5` | Connection pool tuning   |
| `backend/.env`          | `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5`      |                                       |
| `backend/.env`          | `GEMINI_API_KEY`    | –                       | Phase 3. Not used yet. Secret.        |
| shell only              | `TEST_DATABASE_URL` | –                       | Isolated test DB for integration tests |

`ENVIRONMENT` controls development-only features: the seed script and `POST /api/sources`
only work when it is `development` or `test`.

> **Security:** anything prefixed with `VITE_` is shipped to every browser. Never put the Gemini
> key, database credentials or any other secret in the frontend. Secrets belong in
> `backend/.env`, which is git-ignored. Only the `.env.example` files are committed.

## Local development without Docker (optional)

Requires Node.js 24 LTS and Python 3.12.

**Backend**

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head          # needs DATABASE_URL in backend/.env
uvicorn app.main:app --reload --port 8000
```

**Frontend** (in a second terminal)

```bash
cd frontend
npm ci
npm run dev
```

## Quality checks (frontend)

```bash
cd frontend
npm run typecheck     # TypeScript, strict mode
npm run lint          # ESLint
npm run format        # Prettier (write)  ·  npm run format:check to verify only
npm run build         # Production build into dist/
```

To run them inside the container instead: `docker compose exec frontend npm run lint`.

## Adding shadcn/ui components

```bash
cd frontend
npx shadcn@latest add dialog
```

Components are generated into `frontend/src/components/ui/`. Commit them like any other source.
If the container is running, recreate the `node_modules` volume afterwards if the command
installed new packages (see "When dependencies change").

## Roadmap

| Phase | Focus                                                                       | Status   |
| ----- | --------------------------------------------------------------------------- | -------- |
| 1     | Project foundation and Docker                                               | **Done** |
| 2     | Database schema: sources, threads, messages, knowledge, provenance, vectors | **Done** |
| 3     | Simulated live ingestion with automatic Gemini knowledge extraction         | Next     |
| 4     | Vector, keyword and contextual retrieval                                    | Planned  |
| 5     | Evidence-backed guided troubleshooting with React Flow                      | Planned  |
| 6     | Knowledge consolidation, expert feedback and demo polish                    | Planned  |

Details, scope and "done when" criteria for each phase: [docs/roadmap.md](docs/roadmap.md).
