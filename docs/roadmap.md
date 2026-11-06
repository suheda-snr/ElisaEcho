# Elisa Echo – Roadmap

Elisa Echo automatically discovers and preserves operational knowledge from engineers' workplace
communication. See [architecture.md](architecture.md) for how the system works.

Each phase builds on the previous one and keeps the application runnable. The next phase starts
only when the team explicitly decides to begin it.

| Phase | Focus | Status |
| --- | --- | --- |
| 1 | Project foundation and Docker | **Done** |
| 2 | Database schema | **Done** |
| 3 | Simulated live ingestion and automatic knowledge extraction | Next |
| 4 | Vector, keyword and contextual retrieval | Planned |
| 5 | Evidence-backed guided troubleshooting | Planned |
| 6 | Knowledge consolidation, expert feedback and demo polish | Planned |

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

## Phase 3: Simulated live ingestion and automatic extraction

**Goal:** demonstrate the core feature: knowledge discovered automatically from conversations.

**Scope**

- A synthetic conversation dataset of realistic telecom troubleshooting threads, including
  ordinary chatter, unverified suggestions and confirmed resolutions
- A simulated live feed that replays those conversations through the ingestion path
- Gemini-based classification (ordinary / unverified suggestion / confirmed resolution)
- Gemini-based structured extraction validated against Pydantic schemas, with provenance links to
  source messages
- Linking of knowledge items to equipment, incidents and experts
- **Live Discovery page** (repurposed `/capture`): incoming conversations with the knowledge
  identified in them, as it happens
- **Dashboard:** discovered knowledge and recent processing activity

**Done when** a synthetic thread like "service X is failing" → "restart the service, not the
device" → "that worked" automatically produces a confirmed knowledge item that shows its source
messages.

**Out of scope:** real Slack, Teams or email connections.

---

## Phase 4: Retrieval

**Goal:** an engineer describing a new problem finds the relevant past knowledge.

**Scope**

- Embedding generation for knowledge items, stored in pgvector
- Semantic vector search, keyword search on identifiers and error codes, and contextual retrieval
  through linked equipment and incidents
- Ranking that favours confirmed resolutions over unverified suggestions
- **Search page:** results with status, applicability conditions and links to evidence

**Done when** searching with symptoms worded differently from the original conversation returns
the right knowledge item, with its evidence.

---

## Phase 5: Evidence-backed guided troubleshooting

**Goal:** turn retrieved knowledge into an interactive troubleshooting guide.

**Scope**

- Assemble decision trees from related knowledge items
- **Troubleshoot page:** React Flow decision tree where every step shows its supporting
  conversations, contributing experts, status and applicability conditions
- Save an engineer's troubleshooting journey: answers, observations and final resolution
- **Knowledge Graph page:** relationships between incidents, equipment, conversations and
  resolutions

**Done when** an engineer can walk through a tree for a known problem and see the evidence
behind each step.

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
