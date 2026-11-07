# Elisa Echo

AI-powered system that **automatically discovers and preserves hidden operational knowledge** from
the conversations telecom network engineers already have. Built for the Elisa challenge at the
Since AI Hackathon.

> **Status: Phases 1–5 are done.** A simulated live chat feed, **automatic knowledge discovery
> with Gemini**, **hybrid semantic + keyword search** and **evidence-backed guided
> troubleshooting** (interactive decision trees with saved sessions) work end to end. The
> knowledge graph and expert review are **not implemented yet**. See the [roadmap](docs/roadmap.md).

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
| `/discovery`    | Live Discovery                         | Incoming conversations and the knowledge automatically found in them |
| `/search`       | Search Knowledge                       | Hybrid semantic + keyword search with supporting messages            |
| `/troubleshoot` | Guided Troubleshooting                 | Interactive evidence-backed decision trees with saved sessions        |
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
    │   ├── ai/           # Gemini client and structured-output schema
    │   ├── seed/         # Synthetic demo conversations (`python -m app.seed`)
    │   └── core/         # config.py – typed settings
    ├── alembic/          # Migrations: 0001 schema, 0002 full-text index, 0003 guides/sessions
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

- Loads 5 **synthetic** conversations (20 messages) into a "Synthetic NOC chat (demo)" source:
  a confirmed fix (Site 42), irrelevant chatter, an unresolved problem, a thread with several
  competing suggestions, and a second engineer's different fix for similar drops (Site 17).
- Stores **messages only**. No knowledge is pre-extracted; the discovery pipeline finds it.
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
| GET    | `/api/knowledge/{id}`         | Knowledge item with evidence messages, equipment, incidents and discovery details |
| POST   | `/api/guides/generate`        | Evidence-backed troubleshooting guide for a problem (or `insufficient_evidence`) |
| GET    | `/api/guides`, `/api/guides/{id}` | Recent guides / one guide with steps, evidence and sources |
| POST   | `/api/troubleshooting/sessions` | Start a session for a guide                         |
| GET    | `/api/troubleshooting/sessions`, `/{id}` | Recent sessions / one session with path and history |
| POST   | `/api/troubleshooting/sessions/{id}/steps` | Answer, add an observation, or go back      |
| POST   | `/api/troubleshooting/sessions/{id}/complete` | Record the outcome (resolved / unresolved) |
| POST   | `/api/search`                 | Hybrid knowledge search with evidence and ranking signals |
| GET    | `/api/discovery/status`       | Simulation progress, analysis queue, Gemini model, metrics |
| GET    | `/api/discovery/events`       | Pipeline event log (`after` = last seen event id)     |
| GET    | `/api/discovery/threads`      | Threads with their discovery result                   |
| POST   | `/api/simulation/start`, `/stop`, `/reset` | Control the simulated feed (**development/test only**) |
| POST   | `/api/threads/{id}/analyze`   | Analyze one thread now; `?force=true` skips the unchanged check (**development/test only**) |

List endpoints are paginated with `limit` (1–100, default 50) and `offset`, and return
`{items, total, limit, offset}`. There is deliberately **no public endpoint that accepts
messages**: ingestion happens inside the backend (seed script and the simulated feed).

## Live knowledge discovery (Gemini)

The core feature: messages arrive from a (simulated) chat channel, are grouped into conversation
threads, and each thread is analyzed by Google Gemini automatically. Nobody submits knowledge by
hand. The "Start simulation" button only controls the demo feed.

```text
incoming message -> thread (idempotent upsert) -> debounce -> Gemini structured analysis
  -> server-side evidence validation -> knowledge candidate / item / evidence in PostgreSQL
```

### 1. Configure Gemini

Add a key from [Google AI Studio](https://aistudio.google.com/apikey) to `backend/.env`, then
recreate the backend:

```env
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.8-flash
```

```bash
docker compose up -d --force-recreate backend
curl http://localhost:8000/api/discovery/status    # "gemini_configured": true
```

The key stays on the backend; it is never logged or returned by the API.

### 2. Run the demo

1. Open http://localhost:5173/discovery (**Live Discovery**).
2. Click **Reset demo** for a clean start. It deletes only the synthetic demo conversations and
   what was discovered from them.
3. Click **Start simulation**. Messages from four synthetic conversations arrive one by one
   (every 2 s). About 12 s after a conversation goes quiet, Gemini analyzes the whole thread,
   so a demo run costs about 5 Gemini requests, not one per message.
4. Watch the right-hand panel: the lunch chatter is ignored; the Site 42 thread first appears as
   an *unverified suggestion* and becomes *confirmed in conversation* once "That worked" arrives.
   Every fix shows the messages that support it.
5. Click **Start simulation** again: all messages are recognized as duplicates and unchanged
   threads are not sent to Gemini again.

The same from the command line:

```bash
curl -X POST http://localhost:8000/api/simulation/reset
curl -X POST http://localhost:8000/api/simulation/start
curl http://localhost:8000/api/discovery/status          # progress + metrics
curl http://localhost:8000/api/discovery/events          # pipeline log
curl -X POST http://localhost:8000/api/simulation/stop
curl -X POST "http://localhost:8000/api/threads/THREAD_ID/analyze?force=true"   # re-run one thread
```

### 3. Check what was saved

```bash
curl http://localhost:8000/api/discovery/threads   # each thread with its classification
curl http://localhost:8000/api/knowledge           # stored knowledge items
curl http://localhost:8000/api/knowledge/ITEM_ID   # evidence messages, missing info, validation
```

The Dashboard shows the same numbers: messages processed, threads analyzed, candidates,
confirmed resolutions and failures.

### What the pipeline guarantees

- **Classification:** irrelevant / incident without resolution / unverified suggestion /
  confirmed resolution / workaround or exception / contradictory or incomplete.
- **Evidence validation:** Gemini references messages by per-request labels (M1, M2…). The server
  maps them back and drops any reference outside the analyzed thread. Equipment IDs and incident
  numbers must appear literally in the conversation.
- **No invented success:** "confirmed in conversation" requires a message that reports the fix
  worked. Otherwise it is stored as a suggestion and the missing confirmation is recorded.
- **Never auto-approved:** `approval_status` stays `unreviewed`. Model confidence is shown as
  confidence, not verification.
- **Idempotent:** one candidate and item per thread, updated in place as the conversation
  evolves. A fingerprint skips unchanged threads; message ingestion is an upsert.
- **Bounded cost and retries:** per-thread debounce, at most 2 concurrent analyses, at most 3
  Gemini attempts with exponential backoff. Gemini's own `retryDelay` is honoured when it is short;
  a long one (e.g. the free tier's **daily** quota) fails immediately and pauses all Gemini calls
  until the quota resets. Affected threads are marked `failed` instead of guessed, and can be
  re-run from the UI ("Retry analysis") once the quota is back.
- **Prompt-injection resistant:** messages are passed as data, the instructions say to ignore
  instructions inside them, and validation limits what any output can change.

**Free-tier quota tip:** quotas are per model. If `gemini-3.8-flash` is exhausted for the day,
set `GEMINI_MODEL=gemini-3.1-flash-lite` in `backend/.env` and recreate the backend.

### Limitations (hackathon MVP)

- The feed, debounce timers and event log run **inside the API process**. They reset when the
  backend restarts or hot-reloads, and only one backend process is supported. Production would
  use a durable queue and worker (for example a jobs table polled with `SKIP LOCKED`).
  Restarting the simulation resumes safely because delivered messages are skipped as duplicates.
- Only the synthetic demo source is ingested. There are no real Slack or Teams connectors.
- Edited or deleted messages trigger re-analysis. Knowledge that is no longer supported keeps its
  record but loses its evidence and certainty (`resolution_status = unknown`); it is not deleted.
- Equipment rows created from conversations are kept on demo reset (shared reference data).

## Knowledge search (embeddings + hybrid retrieval)

Engineers describe a problem in their own words on the **Search Knowledge** page
(http://localhost:5173/search) and get the previously discovered fix together with the original
messages that support it.

```text
knowledge item -> searchable text -> Gemini embedding (768 dims) -> knowledge_chunks (pgvector)
query -> semantic (cosine) + full-text (PostgreSQL) + exact identifiers -> Reciprocal Rank Fusion
```

### How it works

- **Embeddings:** `GEMINI_EMBEDDING_MODEL` (default `gemini-embedding-2`) at **768 dimensions**,
  the size of the `knowledge_chunks.embedding` column. Documents and queries use the model's
  retrieval task format (text prefixes for gemini-embedding-2, `task_type` for
  gemini-embedding-001); vectors are L2-normalized and their dimension is checked.
- **Searchable text:** title, problem, symptoms, equipment/sites, incidents, root cause,
  resolution (with its confirmation status), attempted actions and applicability conditions. No
  author names or raw chat. Evidence stays separate and is returned with each result. One chunk
  per item for short items; long items are split by section.
- **Automatic indexing:** when discovery creates or updates a knowledge item, its chunk text is
  rewritten and only changed chunks are re-embedded. If the embedding API fails, the knowledge is
  still saved and the chunk stays *pending* (keyword search already works on it).
- **Hybrid ranking:** three separate ranked lists, combined with Reciprocal Rank Fusion
  (`score = Σ weight / (60 + rank)`). Raw cosine and full-text scores are never compared
  directly. Exact identifiers (equipment, site, incident numbers, codes in the text, e.g.
  `PE-03`, `S42-RTR-01`, `INC-1042`, `Site 42`) get double weight.
- **Calibrated semantic cut-off:** semantic matches must reach `SEARCH_MIN_SIMILARITY` (0.65)
  and be within `SEARCH_SIMILARITY_MARGIN` (0.06) of the best match. These values were measured
  on the demo data with gemini-embedding-2 (unrelated queries ≤ 0.62, relevant ≥ 0.68); re-check
  them after changing the model.
- **Honest status:** each response says whether semantic search actually ran (`used`,
  `no_embeddings`, `unavailable`, `not_configured`). If the embedding API is down, keyword and
  identifier search still return results and no similarity is shown.

### Embedding backfill

Knowledge stored before Phase 4 (or chunks left pending by an API outage) is embedded with:

```bash
docker compose exec backend python -m app.scripts.backfill_embeddings --dry-run   # report only
docker compose exec backend python -m app.scripts.backfill_embeddings             # up to 100 chunks
docker compose exec backend python -m app.scripts.backfill_embeddings --limit 20
docker compose exec backend python -m app.scripts.backfill_embeddings --force     # after changing the model
```

It skips unchanged chunks, stops cleanly at the first API or database error (re-run to
continue) and never deletes knowledge or messages.

### Try it

1. Run the demo on **Live Discovery** (Reset demo, then Start simulation) and wait until the
   activity log shows "Embedded for semantic search".
2. Open **Search Knowledge** and click an example, or type the problem in other words, e.g.
   *customers lose their internet sessions every half hour*. The Site 42 fix appears first,
   marked *Confirmed in conversation* and *Not expert-reviewed*, with its four original messages.
3. Search an identifier such as `PE-03` or `S42-RTR-01`.
4. Searches are shareable: the query is kept in the URL (`/search?q=...`).

From the command line:

```bash
curl -X POST http://localhost:8000/api/search -H "Content-Type: application/json" \
  -d '{"query": "connection keeps dropping after router restart", "limit": 5}'
```

Optional filters: `{"filters": {"equipment_identifier": "PE-03", "incident_number": "INC-1042",
"approval_status": "approved", "resolution_status": "confirmed_in_conversation"}}`.

### Security notes and limitations

- Filters and the source `enabled` flag are applied **inside** the retrieval queries. There is
  no per-user authorization yet: every caller can search everything from enabled sources.
  Production needs authentication and per-source access control before real conversations are
  ingested.
- Retrieved messages are untrusted data and are only displayed. Nothing in them is executed or
  interpreted as instructions.
- No AI-generated answer is added on top of the results (the optional grounded explanation was
  not implemented); every statement shown comes from stored knowledge and its source messages.
- Changing `GEMINI_EMBEDDING_MODEL` requires `backfill_embeddings --force` (the model used for
  a stored vector is not recorded per row).

## Guided troubleshooting (evidence-backed decision trees)

On **Guided Troubleshooting** (http://localhost:5173/troubleshoot) an engineer describes a
current problem. Elisa Echo retrieves matching knowledge (Phase 4 hybrid search), Gemini drafts a
decision tree **only from that knowledge and its source messages**, the server validates it, and
the engineer walks through it while every answer and observation is saved.

```text
problem -> hybrid search -> top knowledge + evidence (labelled K#/E#) -> Gemini draft
  -> validation (graph + evidence) -> guide in PostgreSQL -> session (answers, observations, outcome)
```

### What the guide guarantees

- **Grounded:** only knowledge and messages returned by retrieval are sent to Gemini, as untrusted
  data. Every diagnostic, recommendation and resolution step must cite at least one valid source
  message; unknown references are dropped and listed in `validation_notes`.
- **Insufficient evidence:** if no relevant knowledge with evidence is found, Gemini is not called
  and the guide has `status: insufficient_evidence` with no steps. Gemini may also decline.
- **Valid graph:** one start step, acyclic, everything reachable, no dangling or self edges, unique
  answers per step, resolution/escalation steps are end points. An invalid draft gets one retry
  with the specific problems; if it is still invalid nothing is saved (HTTP 502).
- **Status is derived, not generated:** each step's approval status and support level
  (`approved`, `confirmed_in_conversation`, `suggested`, `conflicting`) come from the knowledge
  items it cites. Steps not backed by approved knowledge require manual verification and show a
  change-management warning. Navigation steps (start, question, escalation) get no support label.
- **Multiple experts:** different fixes for similar problems stay separate branches with their
  own sources and conditions; disagreements are flagged as conflicts.
- **Decision support only:** nothing is executed. Session outcomes are the engineer's report and
  never change knowledge approval.

### Try it

1. Make sure discovery has run (Live Discovery: Reset demo, then Start simulation). The demo now
   contains two engineers' fixes for similar drops: Site 42 (restart the DHCP relay service) and
   Site 17 (relay restart did not help; DHCP lease time was misconfigured).
2. Open **Guided Troubleshooting** and click the example *"Customers keep losing their connection
   every half hour, rebooting the router did not help"*, then **Generate guide** (15–60 s).
3. The tree shows separate Site 42 and Site 17 branches, a conflict note and an escalation path.
   Click any step to see its source messages, approval status and applicability.
4. Answer the current step, record an observation, use **Back / revise** (the earlier answer stays
   in the history as superseded), then complete the session as resolved or not resolved.
5. Reload the page: the session (`?session=<id>`) restores the path and full history. Recent
   sessions are listed at the bottom.
6. A problem nothing covers (e.g. a printer paper jam) returns *Not enough evidence* without steps.

From the command line:

```bash
curl -X POST http://localhost:8000/api/guides/generate -H "Content-Type: application/json" \
  -d '{"problem": "Customers drop every 30 minutes, router reboot did not help", "equipment_identifier": "S17-RTR-02"}'
curl -X POST http://localhost:8000/api/troubleshooting/sessions -H "Content-Type: application/json" \
  -d '{"guide_id": "GUIDE_ID"}'
curl -X POST http://localhost:8000/api/troubleshooting/sessions/SESSION_ID/steps -H "Content-Type: application/json" \
  -d '{"type": "answer", "answer_label": "Yes"}'
curl -X POST http://localhost:8000/api/troubleshooting/sessions/SESSION_ID/complete -H "Content-Type: application/json" \
  -d '{"outcome": "resolved", "summary": "Lease time reset; stable"}'
```

### Limitations

- Guide generation calls Gemini once (twice if the first draft is invalid) and is not
  rate-limited per user; there is no authentication yet.
- Guides are snapshots: if the underlying knowledge changes later, existing guides are not
  regenerated (generate a new one).
- The tree layout is a simple deterministic layering; very wide guides need zooming.
- Gemini capacity varies: when a model is overloaded (HTTP 503) generation fails cleanly and can be
  retried; `GEMINI_MODEL` can be switched to another available model.

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
| `backend/.env`          | `GEMINI_API_KEY`    | –                       | Enables discovery. Secret.            |
| `backend/.env`          | `GEMINI_MODEL`      | `gemini-3.8-flash`      | Gemini model with JSON output         |
| `backend/.env`          | `GEMINI_TIMEOUT_SECONDS` / `GEMINI_MAX_ATTEMPTS` | `60` / `3` | Per request / total attempts |
| `backend/.env`          | `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-2` | Must output 768 dims (DB column) |
| `backend/.env`          | `SEARCH_MIN_SIMILARITY` / `SEARCH_SIMILARITY_MARGIN` | `0.65` / `0.06` | Semantic cut-off (calibrated) |
| `backend/.env`          | `SEARCH_CANDIDATE_POOL` | `20`                | Candidates per retriever before fusion |
| `backend/.env`          | `DISCOVERY_DEBOUNCE_SECONDS` | `12`           | Quiet time before analyzing a thread  |
| `backend/.env`          | `DISCOVERY_MAX_CONCURRENT_ANALYSES` | `2`     |                                       |
| `backend/.env`          | `SIMULATION_MESSAGE_INTERVAL_SECONDS` | `2` | Demo feed speed                      |
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
| 3     | Simulated live ingestion with automatic Gemini knowledge extraction         | **Done** |
| 4     | Vector, keyword and contextual retrieval                                    | **Done** |
| 5     | Evidence-backed guided troubleshooting with React Flow                      | **Done** |
| 6     | Knowledge consolidation, expert feedback and demo polish                    | Next     |

Details, scope and "done when" criteria for each phase: [docs/roadmap.md](docs/roadmap.md).
