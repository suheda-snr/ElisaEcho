# Elisa Echo

AI-powered operational knowledge preservation and guided troubleshooting for telecom network
engineers. Built for the Elisa challenge at the Since AI Hackathon.

> **Status: Phase 1 – project foundation.** The app shell, routing, API and Docker setup work.
> AI capture, search, troubleshooting and the knowledge graph are **not implemented yet**; their
> pages explain what is planned.

## Tech stack

| Layer    | Tools                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | React 19, Vite 8, TypeScript 6 (strict), Tailwind CSS 4, shadcn/ui, React Router 8, TanStack Query 5, Axios, Lucide, React Flow, Recharts |
| Backend  | Python 3.12, FastAPI, Uvicorn, Pydantic 2, pydantic-settings, SQLAlchemy 2 (installed, not connected yet), python-dotenv       |
| Dev env  | Docker, Docker Compose, Node.js 24 LTS, npm                                                                                      |

## Project structure

```text
.
├── compose.yaml          # Runs frontend + backend for local development
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
    │   ├── main.py       # App factory, CORS, router registration
    │   ├── api/          # router.py + routes/ (one module per resource)
    │   ├── schemas/      # Pydantic request/response models
    │   ├── services/     # Business logic, called by routes
    │   ├── models/       # SQLAlchemy models (Phase 2)
    │   └── core/         # config.py – typed settings
    ├── requirements.txt
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

## Environment variables

| File                    | Variable            | Default                 | Notes                                 |
| ----------------------- | ------------------- | ----------------------- | ------------------------------------- |
| `frontend/.env`         | `VITE_API_BASE_URL` | `/api`                  | Public. Bundled into browser code.    |
| `backend/.env`          | `APP_NAME`          | `Elisa Echo API`        |                                       |
| `backend/.env`          | `ENVIRONMENT`       | `development`           |                                       |
| `backend/.env`          | `CORS_ORIGINS`      | `http://localhost:5173` | Comma-separated list                  |
| `backend/.env`          | `GEMINI_API_KEY`    | –                       | Phase 2. Optional for now.            |
| `backend/.env`          | `DATABASE_URL`      | –                       | Phase 2. Optional for now.            |

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
pip install -r requirements.txt
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

- **Phase 1 (done):** foundation – app shell, routing, health API, Docker.
- **Phase 2:** Tiger Data PostgreSQL + pgvector connection, SQLAlchemy models, Gemini integration.
- **Later:** knowledge capture, semantic/keyword search, guided troubleshooting decision trees,
  knowledge graph, expert review.
