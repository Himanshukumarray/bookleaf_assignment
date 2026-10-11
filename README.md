# BookLeaf Author Support & Communication Portal

An AI-assisted support platform for a publishing company. Authors raise queries about their books; support staff triage, review an AI-prepared draft, and reply. The AI **proposes** (category, priority, draft reply) and humans **decide**; if the AI is down, everything still works manually.

> Companion docs: [ARCHITECTURE.md](ARCHITECTURE.md) · [AI_DESIGN.md](AI_DESIGN.md) · [ASSIGNMENT_WRITEUP.md](ASSIGNMENT_WRITEUP.md)

## 1. Project overview

Two portals on one modular-monolith backend:

* **Author portal** – dashboard, books (incl. books still in production with null fields), submit a query, ticket list, live conversation.
* **Admin portal** – dashboard, urgency-sorted queue with filters, and a ticket workspace with an AI insights panel, editable AI draft, internal notes and manual overrides for everything.

## 2. Features

* JWT auth, Argon2 password hashing, backend-enforced RBAC and ownership checks, login rate limiting (429).
* Ticket created and committed **before** any AI runs; AI failure never blocks a ticket.
* Gemini structured-output classification + priority in a **single call**, then deterministic priority guardrails.
* RAG over a BookLeaf knowledge base stored in PostgreSQL + **pgvector**, hybrid with category prior.
* Account-grounded drafting (facts from PostgreSQL, conclusions pre-computed from policy), post-generation grounding check.
* Prompt-injection hardening, retries with exponential backoff, per-call observability ledger (`ai_runs`).
* Human-in-the-loop: AI drafts are never sent automatically; sent replies record whether they were AI-assisted.
* WebSocket events → TanStack Query invalidation for live updates.
* Idempotent seed from the supplied JSON; evaluation dataset (25 labelled cases) + offline/live eval harness.

## 3. Screenshots

_Placeholders – run the app and capture:_ `docs/screenshots/author-dashboard.png`, `author-books.png`, `admin-queue.png`, `admin-ticket-workspace.png`.

## 4. Technology stack

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 3, React Router 6, TanStack Query 5, Axios, React Hook Form + Zod, lucide-react, Vitest |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, asyncpg |
| Database | PostgreSQL 16 + pgvector |
| AI | Google Gemini via the official `google-genai` SDK (no LangChain) |
| Real-time | FastAPI WebSockets |
| Tests | pytest, pytest-asyncio, httpx |

## 5. Architecture

```
React ──REST + WebSocket──▶ FastAPI routers ─▶ Services ─▶ Repositories ─▶ PostgreSQL (+pgvector)
                                   │
                                   └─▶ AI Orchestrator ─▶ Classifier · PriorityEngine · Retriever
                                                          ContextBuilder · ResponseGenerator · Grounding
                                                                        │
                                                              AIProvider (interface) ─▶ GeminiProvider
```

Details and Mermaid diagrams: [ARCHITECTURE.md](ARCHITECTURE.md).

## 6. Why a modular monolith

One deployable, one database, one transaction boundary. The AI pipeline is isolated behind an interface and runs *after* commit, so it can be extracted into a worker later without rewriting business logic, but nothing here justifies the operational cost of microservices.

## 7. Project structure

```
bookleaf-support/
├── backend/
│   ├── app/
│   │   ├── main.py                 app factory, wiring (settings, session factory, AI provider, WebSocket manager)
│   │   ├── api/                    dependencies.py (auth/RBAC/DI) + v1/endpoints (auth, books, tickets, admin, ai, ws)
│   │   ├── core/                   config, security (JWT/Argon2), exceptions (error schema), logging, rate_limit
│   │   ├── db/                     base (Base, pgvector type), session, seed
│   │   ├── models/                 SQLAlchemy models (11 tables)
│   │   ├── schemas/                Pydantic request/response models
│   │   ├── repositories/           all SQL lives here
│   │   ├── services/               business rules, authorization, event publishing
│   │   ├── ai/                     providers/, prompts/, classifier, priority, retriever, context_builder,
│   │   │                           response_generator, grounding, royalty, retry, orchestrator, evaluation
│   │   └── realtime/               WebSocket connection manager
│   ├── alembic/                    migrations (0001 = full schema + CREATE EXTENSION vector)
│   ├── data/                       bookleaf_sample_data.json, knowledge_base.json, eval_dataset.json
│   ├── scripts/dev_postgres.py     Docker-free local PostgreSQL+pgvector
│   └── tests/                      unit/ integration/ ai/
├── frontend/src/                   api/ components/ features/ hooks/ pages/ types/ utils/
├── docker-compose.yml              optional PostgreSQL+pgvector
└── *.md
```

## 8. Local prerequisites

* Python 3.11+, Node 20+ (tested with Node 24), npm
* PostgreSQL 14+ **with the pgvector extension** (see §9 for three ways to get one)
* A Gemini API key *(optional – without it everything works except AI suggestions)*

## 9. PostgreSQL setup

**Option A – Docker**
```bash
docker compose up -d db          # pgvector/pgvector:pg16 on localhost:5432, db "bookleaf_support"
```

**Option B – existing PostgreSQL**
```sql
CREATE DATABASE bookleaf_support;
-- the migration runs CREATE EXTENSION IF NOT EXISTS vector (needs pgvector installed on the server
-- and a role allowed to create extensions)
```

**Option C – no Docker, no install (development only)**
```bash
cd backend
pip install pgserver
python scripts/dev_postgres.py   # prints the DATABASE_URL to use; leave it running
```

## 10. Environment variables

`backend/.env` (copy from `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/bookleaf_support` |
| `JWT_SECRET_KEY` | **change it**; ≥32 random chars |
| `GEMINI_API_KEY` | server-side only; leave unset to run without AI |
| `GEMINI_MODEL` / `GEMINI_EMBEDDING_MODEL` | defaults `gemini-2.5-flash` / `gemini-embedding-001` |
| `EMBEDDING_DIMENSIONS` | 768 (must match the `vector(768)` column) |
| `AI_MAX_RETRIES`, `AI_REQUEST_TIMEOUT_SECONDS`, … | retry/timeout/cost knobs, see `.env.example` |
| `CORS_ORIGINS` | e.g. `http://localhost:5173` |

`frontend/.env` (copy from `frontend/.env.example`): `VITE_API_BASE_URL`, `VITE_WS_BASE_URL`. **There is no Gemini key in the frontend, ever.**

## 11. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env   → edit DATABASE_URL, JWT_SECRET_KEY, GEMINI_API_KEY
```

## 12. Database migration

```bash
alembic upgrade head              # creates the pgvector extension and all tables
alembic check                     # (optional) confirms models and migration agree
```

## 13. Dataset seeding

```bash
python -m app.db.seed                       # users, authors, books, availability, KB sections (+ embeddings if GEMINI_API_KEY is set)
python -m app.db.seed --skip-embeddings     # never call Gemini
python -m app.db.seed --embeddings-only     # later: embed KB sections that have no vector yet
python -m app.db.seed --data path/to/other.json
```

Seeding is **idempotent**: re-running upserts by `AUTH…`/`BK…` ids and email; existing passwords are never re-hashed or overwritten. If embeddings can't be generated the app still works (retrieval falls back to category matching). Admins can also call `POST /api/v1/ai/knowledge/embed`.

> **Dataset.** `backend/data/bookleaf_sample_data.json` is the **official BookLeaf-provided sample dataset** (10 authors `AUTH001–AUTH010`, 18 books `BK001–BK018`) and is used unmodified. It intentionally contains nulls (`publication_date`, `mrp`, `author_royalty_per_copy`, `last_royalty_payout_date`, `print_partner`), empty `available_on`, zero sales/royalty, books still in production and below-threshold balances. `python -m app.db.seed` imports it idempotently (upsert by `AUTH…`/`BK…` ids); legitimate nulls are stored as SQL `NULL` and only *displayed* as text such as "Not published yet". The loader reads the nested layout (`authors[].books[]`) and also tolerates a flat `authors[]` + `books[]` layout. `tests/integration/test_seed_integrity.py` fails if any seeded business value differs from this file.

## 14. Frontend setup

```bash
cd frontend
npm install
copy .env.example .env
```

## 15. Running the application

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev          # http://localhost:5173
```

## 16. Demo credentials

These are **application-generated development credentials** created by the seed script (the source JSON has no passwords). Do not use them anywhere real.

| Role | Email | Password |
|---|---|---|
| Admin | `admin@bookleaf.com` | `Admin@123` |
| Author (one per dataset author) | the author's exact email from the dataset, e.g. `priya.sharma@email.com` | `Author@123` |

| Author | Email | Books |
|---|---|---|
| AUTH001 Priya Sharma | priya.sharma@email.com | BK001, BK002 |
| AUTH002 Rohit Kapoor | rohit.kapoor@email.com | BK003, BK004 |
| AUTH003 Ananya Reddy | ananya.reddy@email.com | BK005 |
| AUTH004 Vikram Joshi | vikram.joshi@email.com | BK006, BK007 |
| AUTH005 Meera Nair | meera.nair@email.com | BK008, BK009 |
| AUTH006 Arjun Malhotra | arjun.malhotra@email.com | BK010 |
| AUTH007 Sneha Kulkarni | sneha.kulkarni@email.com | BK011, BK012, BK013 |
| AUTH008 Farhan Sheikh | farhan.sheikh@email.com | BK014 |
| AUTH009 Kavita Deshmukh | kavita.deshmukh@email.com | BK015, BK016 |
| AUTH010 Diya Chatterjee | diya.chatterjee@email.com | BK017, BK018 |

Useful demo scenarios (from the official data): **Kavita / BK016** – ₹850 pending, no payout yet → below the ₹1,000 threshold, so a "where's my royalty?" ticket is *not* treated as overdue (rolls over); **Ananya / BK005** and **Arjun / BK010** – ₹2,546 / ₹2,464 pending and never paid → flagged possibly overdue (HIGH); **Sneha / BK013** and **Kavita / BK015** – books in production with null MRP, publication date and royalty-per-copy, no print partner and no platforms; **Sneha** and **Priya** own several books each.

## 17. API documentation

* Swagger UI: <http://localhost:8000/docs> · ReDoc: <http://localhost:8000/redoc> · Health: `/health`
* All routes under `/api/v1`; errors always look like `{"error": {"code", "message", "details"}}`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me` |
| Author | `GET /author/dashboard`, `GET /books`, `GET /books/{book_id}`, `POST/GET /tickets`, `GET /tickets/{id}`, `GET/POST /tickets/{id}/messages` |
| Admin | `GET /admin/dashboard`, `GET /admin/tickets` (filters: status, category, priority, assignment, author, book, date_from/to, q, sort, page), `GET/PATCH /admin/tickets/{id}`, `POST …/assign`, `POST …/notes`, `POST …/messages` (send response), `POST …/ai-draft`, `POST …/ai-retry` |
| AI ops | `GET /ai/status`, `POST /ai/knowledge/embed` |
| Realtime | `WS /ws?token=<jwt>` |

Status codes: 400 business, 401 unauthenticated, 403 forbidden role, 404 missing **or not yours** (non-disclosing), 409 conflict (closed ticket), 422 validation, 429 login throttling, 503 AI unavailable (admin-triggered AI actions), 500 unexpected (generic message, trace only in server logs).

## 18. AI architecture

`POST /tickets` → validate → save → **commit** → `201` → background task → `AIOrchestrator.process_ticket`:

1. **Classify + prioritise** in one structured-output Gemini call (Pydantic schema → enum category, priority, two confidences, short reason, `needs_human_attention`).
2. **Guardrails** (`PriorityEngine`) adjust the model's priority with deterministic rules (§22).
3. **Retrieve** ≤3 KB chunks (+ the tone guide) via pgvector + category prior.
4. **Build context** from PostgreSQL, scoped to the category (§23).
5. **Draft** a reply; run the **grounding check**; store draft + chunk ids + tokens + latency.
6. Publish `ticket.ai.updated` to staff.

Full detail: [AI_DESIGN.md](AI_DESIGN.md).

## 19. Prompt strategy

Versioned prompt modules (`classification-v1`, `response-v1`) stored with every draft/run. System prompt = role, objective, grounding rules, security rules, tone. User prompt = clearly delimited blocks: `ACCOUNT_CONTEXT`, `KNOWLEDGE_CONTEXT` (trusted) and `<untrusted_ticket>`, `<untrusted_messages>` (data).

## 20. Knowledge retrieval / RAG

KB (`data/knowledge_base.json`) is split into 7 sections, embedded **once** (`gemini-embedding-001`, 768-d, `RETRIEVAL_DOCUMENT`) into `knowledge_chunks.embedding vector(768)`. At query time the ticket text is embedded (`RETRIEVAL_QUERY`) and ranked with pgvector `<=>`; chunks mapped to the ticket's category get a +0.25 boost; non-category chunks must reach cosine ≥ 0.6. Top 3 + `communication_guidelines` are sent — never the whole KB. If embeddings are missing or the embedding call fails, category matching alone is used.

## 21. Structured classification

Output is validated against `ClassificationResult` (enum category/priority, confidences in [0,1], bounded reason). Free-form parsing is never used; a schema violation is a permanent (non-retried) failure.

## 22. Priority guardrails

Model proposes, rules dispose: CRITICAL requires an escalation/legal signal (otherwise capped to HIGH); legal/threat language → CRITICAL; wrong/duplicate ISBN → ≥HIGH; print defects → ≥HIGH; royalty complaints are ≥HIGH only when **data** shows a possibly-overdue balance (≥₹1,000 and >137 days since last payout/publication) and capped at MEDIUM when the balance is below the ₹1,000 threshold; bio updates → LOW. Source is stored (`AI`, `RULE`, `MANUAL`); admins can override anything.

## 23. Grounding strategy

* Account facts come only from PostgreSQL, filtered per category (royalty ticket ⇒ MRP, copies, per-copy royalty, earned/paid/pending, last payout; ISBN ticket ⇒ title/ISBN/status; …).
* Policy conclusions are **pre-computed** (`DERIVED_FACTS`), e.g. "₹850 is below the ₹1,000 threshold, so it rolls over; this is NOT a missed payment" — the model is told, not trusted to infer.
* After generation, every ₹ amount and ISBN in the draft must exist in account/KB text, otherwise the admin sees a "Verify before sending" warning. Amounts quoted by the author are *not* trusted.

## 24. Prompt-injection protection

Author text is wrapped in tags, `<`/`>` are neutralised so it can't close the block or forge section headers, length is capped, and both system prompts say it is untrusted data. Beyond prompting, the architecture limits blast radius: the model can't send anything, can't exceed guardrail priority bounds, and sees only the author's own account data.

## 25. Human-in-the-loop

AI output lands in `ai_drafts`. Only `POST /admin/tickets/{id}/messages` creates a message visible to the author. The UI flags a reply as AI-assisted while it still resembles the draft (word-overlap ≥ 0.3); the API stores `is_ai_assisted` and marks the draft `SENT`.

## 26. Graceful AI degradation

Timeouts, 408/429/5xx ⇒ retried up to `AI_MAX_RETRIES` with exponential backoff (1s, 2s, …, ±10% jitter). 4xx (bad key, invalid request), blocked/empty output and schema failures ⇒ not retried. On final failure: `ai_status = FAILED`, a deterministic keyword-rule priority is applied, the admin sees *"AI assistance temporarily unavailable. You can respond manually."* with **Retry AI analysis**. No key configured ⇒ same behaviour. Stuck `PROCESSING` tickets (worker died) become retryable after 3 minutes.

## 27. AI cost management

One call for classify+priority · KB retrieval, never full KB · category-scoped account fields · last 6 messages, 600 chars each · KB embeddings computed once and reused (changed text invalidates only its own vector) · `max_output_tokens=700` and a 180-word prompt target · no automatic regeneration (admin clicks) · thinking tokens disabled on Flash · deterministic logic (guardrails, royalty maths, fallback priority, grounding) uses no LLM · token usage recorded per call.

## 28. AI observability

`ai_runs` rows (operation, model, prompt version, status, latency, input/output tokens, attempts, error type/message ≤500 chars) per call, `ai_drafts` rows (chunk ids, tokens, latency, grounding warnings) and `ticket_events` audit trail; shown in the admin workspace ("AI run log"). API keys are never logged (logging filter redacts key-like strings).

## 29. Real-time architecture

`ConnectionManager` keeps sockets per user. After a DB commit, `NotificationService` publishes `{type, ticket_id, timestamp}` (no content) to the ticket's author and all admins (AI progress events go to admins only). The React `useTicketSocket` hook invalidates the matching TanStack Query keys; data is re-fetched through the authorised REST API. Reconnects with backoff, 25 s heartbeat, no reconnect loop on auth failure (close code 4401). Queries also poll every 30 s as a safety net.

## 30. Testing

```bash
cd backend
pytest -q                      # 106 tests, no network, no Gemini spend (SQLite + a scripted fake AIProvider)
ruff check app tests scripts
alembic check                  # needs a live PostgreSQL

cd frontend
npm run build                  # tsc + vite build
npm test                       # vitest
```

Live model evaluation against the 25 labelled cases (spends API credits; needs a seeded DB and key):
```bash
python -m app.ai.evaluation --live --free-tier     # quota-safe: sequential, 13s between cases, retries on 429/5xx
python -m app.ai.evaluation --live --start 0 --count 5   # only a subset (0-based start)
python -m app.ai.evaluation --live --delay 0       # paid tier: no pacing
```
Free Gemini keys allow only ~5 requests/minute, so an unpaced run is rate-limited (HTTP 429). The live runner is always sequential, waits `AI_EVAL_DELAY_SECONDS` (default 13) between cases and re-runs the *same* case with backoff (honouring Google's "retry in Ns" hint, capped at 120s, at most `AI_EVAL_MAX_RETRIES` times) on 429/5xx/timeouts. Bad keys and 4xx errors are not retried. Cases that still fail are reported as **API failures**, separate from model quality: accuracy is computed over *completed* cases only, completion is reported on its own, and failed calls are never counted as correct and never replaced by fake output. A run with API failures exits with code 2.

## 31. Known limitations

* **Live Gemini coverage is partial.** With a real (free-tier) key the embeddings and classification calls were verified live (KB embedded, evaluation cases E01–E11 all correct), but free-tier quotas (per-minute and a small per-day cap) prevented a complete 25-case live run in the build session. Re-run `python -m app.ai.evaluation --live --free-tier` with quota available (or a paid key). Model names change over time: if you see 404 "model no longer available", update `GEMINI_MODEL` in `.env`.
* Background work uses FastAPI `BackgroundTasks` (in-process; a restart can drop queued work – admins can retry). WebSocket fan-out and the login limiter are in-memory (single instance).
* Attachments: UI only, nothing is uploaded.
* The migration is a single baseline; there is no ANN index on `knowledge_chunks.embedding` (7 rows – sequential scan is faster).
* JWT is kept in `localStorage` (XSS trade-off) and the WebSocket token travels in the query string (visible in access logs). Production: httpOnly cookie + one-time WS ticket.
* Admin users cannot be created via the UI; there is one seeded admin.

## 32. Production improvements

Redis + RQ/Celery worker for AI jobs and outbox for events; Redis pub/sub for WebSockets; httpOnly refresh-token cookies; per-IP/global rate limits; object storage for attachments; HNSW index when the KB grows; evaluation in CI with a small live smoke set; prompt/response caching; PII redaction before model calls; structured logging + tracing (OpenTelemetry); admin user management and audit UI.

## 33. Deployment suggestions

Backend container (uvicorn/gunicorn workers) behind a reverse proxy with TLS, managed PostgreSQL with pgvector (RDS/Cloud SQL/Neon/Supabase), secrets from a secret manager, run `alembic upgrade head` as a release step, frontend built with `npm run build` and served from a CDN/static host with `VITE_API_BASE_URL` pointing at the API, CORS limited to that origin.

### Troubleshooting (Windows)

If Windows *Application Control / Smart App Control* blocks a compiled wheel (symptom: `DLL load failed … blocked this file` when importing `sqlalchemy` or `asyncpg`), reinstall SQLAlchemy pure-Python: `set DISABLE_SQLALCHEMY_CEXT=1 && pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy[asyncio]`, or install a different `asyncpg` wheel version.
