<p align="center">
  <img src="docs/images/logo.png" alt="Elisa Echo" width="340">
</p>

<p align="center">
  <b>Evidence-backed operational knowledge, captured from the conversations network engineers already have.</b><br>
  Prototype for the Elisa challenge, Since AI Hackathon 2026.
</p>

<p align="center">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white">
  <img alt="TypeScript 6" src="https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white">
  <img alt="Vite 8" src="https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white">
  <img alt="Tailwind CSS 4" src="https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white">
  <img alt="FastAPI on Python 3.12" src="https://img.shields.io/badge/FastAPI-Python_3.12-009688?logo=fastapi&logoColor=white">
  <br>
  <img alt="Tiger Data" src="https://img.shields.io/badge/Tiger_Data-hosted_PostgreSQL-F5A623?logo=timescale&logoColor=white">
  <img alt="PostgreSQL with pgvector" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white">
  <img alt="Google Gemini" src="https://img.shields.io/badge/Google_Gemini-AI-8E75B2?logo=googlegemini&logoColor=white">
  <img alt="Slack Socket Mode" src="https://img.shields.io/badge/Slack-Socket_Mode-4A154B?logo=slack&logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

---

## Table of contents

1. [Overview](#overview)
2. [Implemented capabilities](#implemented-capabilities)
3. [Example: knowledge reuse (synthetic scenario)](#example-knowledge-reuse-synthetic-scenario)
4. [How Elisa Echo works](#how-elisa-echo-works)
5. [Knowledge intelligence: core technical principles](#knowledge-intelligence-core-technical-principles)
   - [Knowledge detection: relevant or not?](#knowledge-detection-relevant-or-not)
   - [Evidence validation](#evidence-validation)
   - [Entity linking](#entity-linking)
   - [Embeddings and hybrid retrieval](#embeddings-and-hybrid-retrieval)
   - [Knowledge relationships and validity](#knowledge-relationships-and-validity)
   - [Guided troubleshooting](#guided-troubleshooting)
   - [Outcome feedback](#outcome-feedback)
   - [Failure handling](#failure-handling)
6. [Technical architecture](#technical-architecture)
7. [Integrations](#integrations)
8. [Installation and local setup](#installation-and-local-setup)
9. [Testing and current limitations](#testing-and-current-limitations)
10. [Further documentation](#further-documentation)

---

## Overview

Much of what keeps a network running is never written down. A field engineer swaps an optical
module, the link comes up, and traffic still does not flow. A colleague answers in chat: "on these
older units, disable and re-enable the interface; don't reboot." The fix works, the thread
scrolls away, and the next engineer facing the same symptom starts from scratch. Monitoring
records that a link failed, not why, and documentation is rarely updated after the fact.

Elisa Echo reads the conversation channels a team already uses. It finds the threads that hold
operational knowledge and turns them into structured records with three properties:

- every claim points back to the messages it came from;
- the record is bound to the network entities it concerns (node, unit class, site, event);
- the record carries a validity period.

Engineers retrieve these records in their own words, follow them as step-by-step troubleshooting
guides, and report whether they worked. Nobody has to fill in a form.

> [!NOTE]
> **Slack is connected today:** messages from monitored channels are captured live.
> **Microsoft Teams, Discord and Google Chat are future integrations.** They will feed the same
> pipeline, but they are not connected yet.

## Implemented capabilities

| Page | What works |
| --- | --- |
| **Live Discovery** | Incoming threads, highlighted evidence messages, the extracted knowledge with entity chips, and retry for failed analyses |
| **Knowledge Explorer** | Hybrid search with "Valid on" and "Include outdated"; every item with its evidence, links, validity and feedback; groups of related cases with side-by-side comparison and conflicts |
| **Troubleshooting** | Evidence-backed decision trees (step-by-step or tree view), saved sessions with back-tracking and notes, and "Did it work?" outcome reports |
| **Integrations** | Slack connection status and channel allowlist, the synthetic inventory, connector activity |

<table>
  <tr>
    <td width="50%"><img src="docs/images/live-discovery.png" alt="Live Discovery showing the TRN-042 conversation with evidence highlighted and the discovered knowledge"><br><sub>Live Discovery: evidence messages and the extracted knowledge with entity links</sub></td>
    <td width="50%"><img src="docs/images/knowledge-item.png" alt="Knowledge item with validity, entity links, conditions and attempted actions"><br><sub>Knowledge item: validity, entity links, conditions, what was tried</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/images/relationships.png" alt="Related cases grouped and compared side by side"><br><sub>Related cases grouped and compared</sub></td>
    <td width="50%"><img src="docs/images/troubleshooting-tree.png" alt="Troubleshooting decision tree with source messages"><br><sub>Decision tree; each step shows its source messages</sub></td>
  </tr>
</table>

## Example: knowledge reuse (synthetic scenario)

*The TRN-042 conversation reproduces Appendix A of the Elisa challenge brief. The network
inventory is synthetic.*

1. **The conversation.** In a Teams-style chat, a field engineer reports that after an SFP
   replacement on transmission node **TRN-042** the link is up but no traffic flows. An expert
   asks whether it is one of the older units ("installed around 2019"). The expert advises
   disabling and re-enabling the interface instead of rebooting, and the engineer confirms that
   traffic recovered.
2. **The record.** The item is stored as `confirmed_in_conversation`. Its evidence is the
   problem report, the suggestion with its applicability condition, and the confirmation.
3. **The links.** Because the expert said the advice applies to the older units, the item is
   linked to:
   - TRN-042 (`observed_on`);
   - its site SITE-OULU-07 (`located_at`, from the inventory);
   - the **TX-900 legacy unit class** (`applies_to`);
   - the event "SFP replacement" (`triggered_by`).
4. **The reuse.** A later search for *"TRN-118: port up after optical module swap, but zero
   traffic"* returns the TRN-042 item, even though TRN-118 appears in no conversation. The
   identifier retriever finds TRN-118 in the inventory, sees the shared TX-900 class and adds
   the signal "trn118 (same unit class)". The newer TRN-305 (TX-2000 class) does not inherit
   the fix. A guide generated for TRN-118 proposes checking the traffic counters and toggling
   the interface, and each step cites the original messages.

<p align="center">
  <img src="docs/images/search-trn118.png" alt="Knowledge Explorer search for TRN-118: port up after optical module swap, but zero traffic, returning the TRN-042 fixes with the TX-900 unit class link, confirmed in chat, needs review" width="860"><br>
  <sub>Searching for TRN-118, a node no conversation mentions, returns the TRN-042 fixes through the shared TX-900 unit class.</sub>
</p>

**Temporal validity.** A 2025 message says the barrier key for **SITE-PELLO-03** is in a
lockbox; a 2026 chat says it has moved to the depot. Consolidation marks the 2025 item as
superseded (`valid_to` 2026-10-28). Search returns the current instruction, and with **Valid
on** `2025-06-01` it returns the old one.

<p align="center">
  <img src="docs/images/outdated-knowledge.png" alt="Outdated knowledge item for SITE-PELLO-03: valid from March 12 until October 28, replaced by the updated barrier key location, with the reason the newer case gives" width="720"><br>
  <sub>The 2025 instruction stays visible but is marked outdated: when it was valid, which item replaced it, and why.</sub>
</p>

## How Elisa Echo works

<p align="center">
  <img src="docs/images/how-it-works.png" alt="How Elisa Echo works: sources, ingestion filter, threads, Gemini classification and extraction, server validation (rejected, incomplete or accepted), link and store, knowledge store, embedding and indexing, hybrid search, guide generation, guide validation and outcome feedback, with related-case grouping and validity updates" width="900">
</p>

**Ingestion.** Messages are stored unchanged, with their author, timestamp and permalink. They are
grouped into threads: a Slack thread or a demo chat conversation. Re-delivered messages are de-duplicated, and edits and deletions re-trigger
analysis.

**Analysis timing.** A thread is analyzed once it has been quiet for 12 seconds, so a burst of
messages costs one Gemini call. A content fingerprint skips threads that have not changed. Each
of the remaining stages is explained below.

## Knowledge intelligence: core technical principles

### Knowledge detection: relevant or not?

Relevance is decided in three steps: a rule-based filter, Gemini's judgement, and a
deterministic server-side gate. There is no separate classifier model and no keyword list.

**1. Ingestion filter (rules).** Only allowlisted sources are stored. From Slack, the following
are dropped before any AI call: bot messages (including Elisa Echo's own), system events (joins,
topic changes), DMs and empty messages (`backend/app/slack/events.py`).

**2. Gemini classification (judgement).** Gemini returns:

- exactly one classification, defined in the system prompt
  (`backend/app/services/discovery/prompt.py`):

  | Classification | Meaning in the prompt |
  | --- | --- |
  | `irrelevant` | No operational content (greetings, lunch, small talk) |
  | `incident_without_resolution` | A technical problem is discussed, but no fix is proposed |
  | `unverified_suggestion` | A fix is proposed, but nobody confirms it worked |
  | `confirmed_resolution` | A message explicitly reports the fix worked |
  | `workaround_or_exception` | Know-how such as "don't do X in situation Y", even without a full fix |
  | `contradictory_or_incomplete` | Conflicting or too unclear to rely on |
  | `access_information` | How to physically reach a site (keys, gate codes, contacts) |

- an `is_valuable_knowledge` flag, true "only if another engineer could reuse this to
  troubleshoot later";
- a short rationale and a confidence score, which are stored for auditing;
- the extracted content: symptoms, attempted actions with their outcomes, the resolution,
  applicability conditions and a scope (`this_equipment_only` or `same_equipment_class`).

**How Gemini can make this decision.** Step 2 is *zero-shot classification* by a large language
model. Gemini was pre-trained on large amounts of text, so it already models language
understanding: what a symptom, a proposed fix, a confirmation or a greeting looks like, and how
a reply relates to an earlier question. Elisa Echo does not train or fine-tune a model. It turns
that general ability into a narrow task:

- **Definitions instead of training data.** The system prompt defines each category and the
  rules (for example "`confirmed_resolution` only if a message explicitly says the fix worked").
- **Whole-thread context.** All messages arrive together and in order, as untrusted JSON data,
  so a late "that worked" changes how the earlier suggestion is read.
- **Constrained output.** The Pydantic schema is sent as Gemini's `response_schema` with
  `response_mime_type="application/json"` (`backend/app/ai/gemini.py`). The model can only
  answer with one of the 7 allowed labels and the defined fields. The reply is validated against
  the same schema again.
- **Low randomness.** Temperature 0.1 makes repeated analyses of the same thread consistent.

The model's judgement is not trusted on its own: step 3 decides what is stored. Its accuracy
has not been measured on a labelled dataset.

**3. Server gate (deterministic).** `validate_analysis()` in
`backend/app/services/discovery/validation.py` decides the outcome:

| Outcome | Condition | UI label |
| --- | --- | --- |
| **Rejected** | `is_valuable_knowledge` is false, or the classification is `irrelevant` | Not relevant |
| **Incomplete** | Valuable, but the classification is `incident_without_resolution` or `contradictory_or_incomplete`, or no valid evidence or content remains | No fix yet (kept as a candidate, not a knowledge item) |
| **Accepted** | One of the four knowledge classifications (suggestion, confirmed, workaround, access) **and** at least one valid evidence message **and** a resolution, attempted action or condition | Knowledge |

The full analysis is kept for every thread, including rejected ones: the classification,
rationale, model name and validation flags. Each decision can therefore be inspected later.

### Evidence validation

Messages are sent to Gemini with per-request labels (M1, M2, …). Every cited message carries a
role:

- `problem_report`
- `attempted_fix`
- `suggested_solution`
- `confirmed_resolution`
- `applicability_condition`

The server maps the labels back to stored message IDs and discards any reference outside the
thread. Equipment, site and incident identifiers must appear literally in the conversation.

**How "it worked" is recognised.** A resolution stays `confirmed_in_conversation` only if at
least one valid cited message has the `confirmed_resolution` role. Otherwise it is downgraded to
`suggested`, successful outcomes become `unknown`, and "confirmation that the fix worked" is
recorded as missing. Even then, a confirmation means that one engineer reported success, not
that an expert approved it.

### Entity linking

Binding is deterministic and happens after validation (`backend/app/services/entities.py`):

- A verified equipment ID such as `TRN-042` is linked as `observed_on`.
- Its site comes from the inventory (`located_at`).
- Its unit class (`TX-900`) is linked as `applies_to` **only** when the extracted scope says
  the knowledge applies to that kind of unit. A device-specific fix stays bound to one device.
- Sites mentioned in access knowledge are linked as `access_to`.
- Operational events (for example "SFP replacement") are linked only if every word appears in
  the thread.

Each link records whether it came from the conversation or the inventory.

### Embeddings and hybrid retrieval

The embedded text is a deterministic summary of the item: title, problem, symptoms, equipment,
root cause, resolution with its confirmation status, and conditions. It contains no author names
and no raw chat.

`gemini-embedding-2` produces 768-dimension vectors. They are L2-normalized and stored in
pgvector with an HNSW cosine index, so similar meaning gives a high cosine similarity even with
different wording. Semantic matches must reach 0.65 similarity and lie within 0.06 of the best
match.

Two more retrievers run alongside semantic search: PostgreSQL full-text search, and exact
identifier matching, which includes the shared unit class. The three rankings are combined with
Reciprocal Rank Fusion (k = 60, identifier weight 2), because embeddings handle paraphrase well
but equipment codes poorly.

### Knowledge relationships and validity

**Candidate selection.** After indexing, each item is compared with at most six candidates.
Candidates are items with embedding similarity of at least 0.6, or items that share an equipment,
node or site identifier. Items are never compared all-pairs.

**Pair comparison.** Gemini compares each pair with the same constrained-output technique as
detection. It returns one of these relationships, with the shared symptoms, the condition
differences and cited messages:

- `same_problem`
- `supporting_evidence`
- `same_problem_different_conditions`
- `different_outcome`
- `potentially_conflicting`
- `related_symptoms`
- `unrelated`

**Validation.** A grouping relationship without evidence on both sides is downgraded to
`related_symptoms`. An item joins a group only if it is strongly related to every member, so
grouping never chains. Originals are never merged.

**Replacement and validity.** Gemini may say that one case replaces the other. The server
accepts this only if the cases are related, both cite evidence, and the replacing case's
evidence is newer. The older item then gets `valid_to` and `superseded_by`; it is not deleted.
Search returns currently valid knowledge by default, and can include outdated items or answer for
a past date (`as_of`).

### Guided troubleshooting

**Input.** A problem description is run through hybrid search. The top four supported
knowledge items are kept, together with up to three related group members, their relationships,
inventory facts and earlier outcome reports. These, with their evidence messages labelled K#
and E#, are the only material Gemini sees. If nothing relevant is found, the result is
`insufficient_evidence` and Gemini is not called.

**Drafting.** Gemini drafts a decision tree under a schema. Nodes can only be `start`,
`question`, `diagnostic`, `recommendation`, `resolution` or `escalation`.

**Validation.** The server checks that the draft:

- has exactly one start step;
- has no cycles and no dangling edges;
- has every step reachable from the start;
- has unique answers per step;
- cites valid evidence on every action step.

An invalid draft gets one retry with the specific problems listed. If it is still invalid,
nothing is saved.

**Trust labels.** Each step's support level and approval status are derived from the knowledge
it cites, never generated by the model.

### Outcome feedback

After a recommendation, the engineer answers **Did it work?**: attempted or not, and resolved,
not resolved, partially resolved or unknown. Equipment and firmware are optional. Each report
is stored as a separate, `self_reported` kind of evidence, one per session, step and item; edits
require a one-time token.

Reports are aggregated per knowledge item, firmware and equipment. A success rate is shown only
from 5 attempts. The aggregates are included in new guide prompts, so a guide can ask for the
firmware or warn where an action was reported as failing. Feedback never changes a knowledge
item's resolution or approval status.

### Failure handling

- **Analysis.** Gemini errors are retried a bounded number of times, with backoff. A thread
  that still fails is marked `failed`, nothing is guessed, and **Retry analysis** appears. A
  daily-quota error pauses all Gemini calls until the quota resets.
- **Search.** If embeddings are unavailable, search continues with keyword and identifier
  matching. The response and the UI say that semantic search did not run.
- **Indexing and grouping.** An embedding or comparison failure leaves the knowledge saved. The
  item is marked for retry.
- **Guides.** No evidence means no Gemini call. An invalid or failed draft is not stored.

## Technical architecture

| Component | Technology | Responsibility in Elisa Echo |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Flow | Live Discovery, Knowledge Explorer, decision-tree rendering. Calls only relative `/api` URLs through the Vite proxy |
| API and pipeline | FastAPI (Python 3.12), SQLAlchemy 2 async, Pydantic | REST API, in-process debounced analysis queue, validation, entity binding, guide sessions |
| AI extraction | Google Gemini (`gemini-3.1-flash-lite` configured) with structured output | Thread classification and extraction, pair comparison, group summaries, decision-tree drafts |
| Embeddings | `gemini-embedding-2`, 768 dimensions | Document and query vectors for semantic search and candidate selection |
| Relational storage | PostgreSQL (Tiger Data hosted), Alembic migrations `0001`–`0008` | Messages, knowledge, evidence, entity links, relationships, guides, sessions, feedback |
| Vector retrieval | pgvector (HNSW, cosine) + PostgreSQL full-text (GIN) | Semantic and keyword retrievers inside the same SQL queries as the source filters |
| Integration worker | `slack-sdk` Socket Mode (separate `slack-worker` service) | Live Slack capture from allowlisted public channels |
| Development infrastructure | Docker Compose, pytest, ESLint, TypeScript strict | Local three-service stack, backend tests against an isolated pgvector database |

## Integrations

| Source | Status | Details |
| --- | --- | --- |
| Slack | **Live** | Socket Mode worker. Read-only scopes (`channels:history`, `channels:read`, `users:read`). Public channels on an explicit allowlist. Threads, edits and deletions are synchronized |
| Teams-style demo conversations | **Synthetic** | Demo feed (`/api/simulation/start`): TRN-042, SITE-PELLO-03, Site 17/42/58, BGP, OLT and an irrelevant lunch thread |
| Network inventory | **Synthetic** | 6 sites and 6 nodes, including TRN-042/118 (TX-900) and TRN-305 (TX-2000) |
| Microsoft Teams, Discord, Google Chat | **Future** | Planned to feed the same pipeline. Shown on the Integrations page as previews ("not connected"); no connector code exists yet |

## Installation and local setup

**Requirements:**

- Git and Docker Desktop (or Docker Engine with the Compose plugin);
- a [Gemini API key](https://aistudio.google.com/apikey);
- a PostgreSQL database with pgvector ([Tiger Data](https://console.cloud.timescale.com/) or
  the local container below).

**1. Clone and configure.**

```bash
git clone <repository-url> ElisaEcho && cd ElisaEcho
cp backend/.env.example backend/.env      # PowerShell: Copy-Item backend/.env.example backend/.env
```

Set these values in `backend/.env`. The file is git-ignored. Never put secrets in
`frontend/.env`, because `VITE_` variables reach the browser.

```env
ENVIRONMENT=development
DATABASE_URL=postgres://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

All optional settings (Slack, search thresholds, pipeline tuning) are documented in
[`backend/.env.example`](backend/.env.example).

<details>
<summary>No Tiger Data account: use a local pgvector container</summary>

Run this after step 2, so that the `elisa-echo_default` network exists:

```bash
docker run -d --name elisa-echo-db --network elisa-echo_default \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=elisa_echo \
  -v elisa-echo-db-data:/var/lib/postgresql/data pgvector/pgvector:0.8.7-pg17-trixie
```

Set `DATABASE_URL=postgresql+psycopg://postgres:postgres@elisa-echo-db:5432/elisa_echo`, then run
`docker compose up -d --force-recreate backend slack-worker`.
</details>

**2. Start the services and create the schema.**

```bash
docker compose up --build -d                       # backend, slack-worker, frontend
docker compose exec backend alembic upgrade head   # enables the pgvector extension and creates the schema; re-run after pulling
curl http://localhost:8000/api/health/db           # {"status":"ok","database":"connected","pgvector":true,...}
```

**3. Load the synthetic demo data.** This streams the synthetic demo conversations through the
real pipeline, and takes a few minutes and about a dozen Gemini calls:

```bash
curl -X POST http://localhost:8000/api/simulation/start   # Windows PowerShell: use curl.exe
```

**4. Open the app.**

| What | URL |
| --- | --- |
| Application | <http://localhost:5173> |
| API and Swagger UI | <http://localhost:8000/docs> |
| Pipeline status | <http://localhost:8000/api/discovery/status> |

After editing `backend/.env`, run `docker compose up -d --force-recreate backend slack-worker`
(a plain restart does not reload it). To connect Slack, follow [docs/slack-setup.md](docs/slack-setup.md). The app can be created from
[docs/slack-app-manifest.yaml](docs/slack-app-manifest.yaml).

## Testing and current limitations

The backend has unit tests and integration tests (`backend/tests/`). They cover:

- discovery and validation rules;
- search, including the fallback when embeddings are unavailable;
- entity binding and validity;
- consolidation (including non-transitive grouping);
- guide graph validation;
- sessions and feedback;
- Slack behaviour, including that tokens are never returned;
- seed safety.

Gemini and Slack are replaced by fakes, so the tests verify pipeline logic and safeguards,
not model accuracy. The last full run, against an isolated pgvector database on 7 Nov 2026,
passed 343 tests. The frontend is checked with strict TypeScript and ESLint; there are no
frontend or end-to-end tests.

```bash
docker compose exec backend pytest                 # unit tests; integration tests are skipped without a test DB
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@<test-db-host>:5432/elisa_echo_test backend pytest
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
```

Integration tests rebuild the schema and refuse to run unless the database name contains `test`.

**Limitations:**

- **No production access control.** There is no authentication, and no per-user or per-source
  permissions. Administrative actions are gated only by `ENVIRONMENT=development`.
- **No expert approval workflow.** Every item remains "Needs review", and feedback is
  self-reported only.
- **Integration maturity.** Slack is limited to a single workspace and public channels, with no
  history backfill. Teams, Discord and Google Chat are future integrations. The inventory is
  synthetic.
- **Prototype runtime.** Analysis scheduling is in-process, so a backend restart drops queued
  analyses (start the demo feed again to re-queue them). It runs locally only.
- **No accuracy benchmarks.** No precision, recall or time-saving figures have been measured.
  The search thresholds were calibrated on the small demo dataset.
- **Data handling.** Message text is sent to the Gemini API, with no PII redaction.

## Further documentation

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Original design: discovery workflow, data model and table descriptions. Written before the Slack and consolidation work, so the code takes precedence where they differ |
| [docs/slack-setup.md](docs/slack-setup.md) | Step-by-step Slack app setup and troubleshooting |
| [docs/slack-app-manifest.yaml](docs/slack-app-manifest.yaml) | Slack app manifest: Socket Mode, read-only scopes, `message.channels` |
| [docs/roadmap.md](docs/roadmap.md) | Development phases |
| [backend/.env.example](backend/.env.example) | Every configuration variable with defaults |
| <http://localhost:8000/docs> | Live OpenAPI reference for all endpoints (when running) |
