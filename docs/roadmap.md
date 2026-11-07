# Elisa Echo – Roadmap

Elisa Echo automatically discovers and preserves operational knowledge from engineers' workplace
communication. See [architecture.md](architecture.md) for how the system works.

Each phase builds on the previous one and keeps the application runnable. The next phase starts
only when the team explicitly decides to begin it.

| Phase | Focus | Status |
| --- | --- | --- |
| 1 | Project foundation and Docker | **Done** |
| 2 | Database schema | **Done** |
| 3 | Simulated live ingestion and automatic knowledge extraction | **Done** |
| 4 | Vector, keyword and contextual retrieval | **Done** |
| 5 | Evidence-backed guided troubleshooting | **Done** |
| 6 | Knowledge consolidation, expert feedback and demo polish | Next |

---

## Phase 1: Project foundation and Docker (done)

**Delivered**

- React + Vite + TypeScript frontend with Tailwind CSS, shadcn/ui, React Router, TanStack Query,
  Axios, Lucide, React Flow and Recharts
- App layout with sidebar, header and a responsive mobile menu; five routes with placeholder pages
- FastAPI backend with typed settings, environment-based CORS and `GET /api/health`
- Docker Compose development setup with hot reload for both services
- Vite proxy so the browser only uses relative `/api` URLs

**Carried forward unchanged:** Docker setup, API client, routing, layout and backend structure.

---

## Phase 2: Database schema (done)

**Goal:** a PostgreSQL schema that can hold communication data, extracted knowledge and its
provenance.

**Delivered**

- Async SQLAlchemy 2 + psycopg 3 connection to Tiger Data via `DATABASE_URL`, with pooling,
  `pool_pre_ping`, connect timeouts and secret-free error messages
- Alembic migration `0001` that enables pgvector and creates 11 tables: communication sources,
  conversation threads, messages, knowledge candidates, knowledge items, knowledge evidence,
  equipment, incidents, two association tables and knowledge chunks with `vector(768)` + HNSW index
- Idempotent ingestion service (upserts on external IDs, edit/deletion synchronization)
- Read-only APIs for sources, threads, messages and knowledge; `POST /api/sources` limited to
  development; `GET /api/health/db`
- Safe, idempotent seed script with 4 synthetic conversations (messages only)
- Unit tests plus integration tests against an isolated test database

**Design notes**

- Experts are represented by message authors (`author_external_id`, `author_display_name`) for
  now; a dedicated `experts` table can be added in Phase 6 if expert review needs it.
- The embedding dimension is fixed at 768. Phase 4 must request this size explicitly.

**Out of scope (unchanged):** Gemini calls, embedding generation, frontend changes.

---

## Phase 3: Simulated live ingestion and automatic extraction (done)

**Goal:** demonstrate the core feature: knowledge discovered automatically from conversations.

**Delivered**

- Gemini client (`google-genai`, model from `GEMINI_MODEL`, default `gemini-3.8-flash`) with
  structured Pydantic output, timeouts and bounded exponential-backoff retries
- Six-way classification: irrelevant, incident without resolution, unverified suggestion,
  confirmed resolution, workaround/exception, contradictory/incomplete
- Server-side validation: message references limited to the analyzed thread, identifiers must
  appear in the text, confirmations need a confirming message, approval never set automatically
- One candidate and one knowledge item per thread, updated in place as the thread evolves;
  fingerprinting skips unchanged threads; evidence and equipment links kept in sync
- In-process simulated feed (round-robin across threads), per-thread debounce, concurrency limit,
  event log; start / stop / reset (development only)
- Live Discovery page (`/discovery`, replaces `/capture`) and real metrics on the Dashboard
- Unit tests with mocked Gemini and integration tests on an isolated database

**No migration was needed:** the analysis fingerprint and raw model output live in
`knowledge_candidates.extracted_data`.

**Known limitations:** the pipeline state lives in the API process (single process, lost on
restart); only the synthetic source is connected. See the README for details.

---

## Phase 4: Retrieval (done)

**Goal:** an engineer describing a new problem finds the relevant past knowledge.

**Delivered**

- Gemini embeddings (`GEMINI_EMBEDDING_MODEL`, default `gemini-embedding-2`, 768 dimensions to
  match the database) with retrieval task formats, dimension checks and normalization
- Deterministic searchable text per knowledge item; one chunk per short item, section-based
  splitting for long ones; only changed chunks are re-embedded
- Automatic indexing after discovery; embedding outages leave chunks pending, retried by
  `python -m app.scripts.backfill_embeddings` (bounded, idempotent, `--dry-run` / `--force`)
- Hybrid retrieval: pgvector cosine search + PostgreSQL full-text search (GIN index, migration
  0002) + exact identifier matching, fused with Reciprocal Rank Fusion
- `POST /api/search` with filters applied inside the queries, evidence (author, time, source,
  excerpt) and transparent ranking signals; keyword fallback when embeddings are unavailable
- Search Knowledge page with example queries, filters, shareable `?q=` URLs and a detail view
  showing the original supporting messages

**Not done:** the optional Gemini-written explanation of each match (results show only stored
knowledge and messages); per-user authorization.

---

## Phase 5: Evidence-backed guided troubleshooting (done)

**Goal:** turn retrieved knowledge into an interactive troubleshooting guide.

**Delivered**

- Guide generation: Phase 4 hybrid retrieval -> Gemini draft (structured output) built only from
  the retrieved knowledge and messages -> server-side validation of graph and evidence -> stored
- `insufficient_evidence` response without calling Gemini when nothing relevant is known
- Derived approval status and support level per step; manual-verification and change-management
  warnings for anything not expert-approved; conflicting evidence flagged
- Multiple experts' fixes kept as separate branches (demo: Site 42 vs. Site 17)
- Migration 0003: troubleshooting_guides, guide_nodes, guide_edges, node_evidence,
  troubleshooting_sessions, session_steps (additive)
- Sessions with append-only steps (answers, observations, back/revise as superseded history),
  completion with outcome summary; outcomes never change knowledge approval
- Guided Troubleshooting page: problem form, React Flow decision tree with active path, current
  step with answers, evidence panel, history, recent sessions, reloadable `?session=` URLs

**Not done:** per-user authorization and rate limiting; regenerating guides when knowledge changes.

---

## Phase 6A: Real Slack integration (done)

- `slack-worker` service: Socket Mode listener (slack-sdk), credential check, heartbeat,
  automatic reconnect, immediate acknowledgement and ordered processing
- Channel allowlist on communication sources; Slack threads mapped to conversation threads;
  idempotent ingestion, edit and deletion handling, bot/system message filtering
- Reuses the existing discovery engine (debounced Gemini analysis), embeddings, search and guides
- Migration 0004 (integration_state, integration_events); Integrations page; status/channels/
  events/health API

---

## Phase 6: Consolidation, expert feedback and demo polish

**Goal:** make the knowledge base trustworthy over time and prepare the demo.

**Scope**

- Consolidate related knowledge from multiple experts into alternative troubleshooting paths
- Expert review: approve, correct or reject extracted knowledge
- End-to-end demo script with synthetic data
- UI polish, empty states, error handling and performance checks

**Done when** the full story runs end to end: conversation → discovery → search → guided
troubleshooting → expert review.

---

## Explicitly not planned (for now)

- Connections to real Slack, Microsoft Teams or email accounts
- Manual knowledge submission forms (automatic discovery is the core feature)
- Additional infrastructure such as message queues, Redis, Kubernetes or a separate worker service
