# Assignment Write-up – BookLeaf Author Support Portal

**What I prioritised.** The brief weights AI integration and architecture equally, so I spent effort where a real support team would feel it: the ticket must never depend on the model, the model must not be able to say something false to an author, and an admin must always be able to take over. UI polish was deliberately second; the admin ticket workspace got the most care.

**Architecture.** A modular monolith: FastAPI → services → repositories → PostgreSQL, with an `ai/` package behind an `AIProvider` interface (Gemini is one implementation, used through the official SDK, no LangChain). Authorization lives in services/dependencies, not in React. Ticket creation commits first, returns `201`, and only then schedules the AI pipeline as a background task. One test even runs with no AI provider at all and still creates and handles tickets.

**AI decisions.**
* *One structured call* returns category, priority, two confidences and a short reason (Pydantic schema → Gemini `response_schema`), which is cheaper and simpler to validate than prose parsing.
* *Priority is hybrid.* The model proposes; deterministic rules set floors (ISBN errors, print defects, evidenced overdue royalties, legal threats) and ceilings (CRITICAL needs an escalation signal; sub-threshold royalty balances cap at MEDIUM). Source is stored as AI / RULE / MANUAL, and manual overrides are never overwritten by a retry.
* *Grounding over cleverness.* Account facts come from PostgreSQL filtered by category; policy conclusions are computed in code and handed to the model (₹850 pending vs the ₹1,000 threshold is "rolls over, not missed"). A post-generation check flags any ₹ amount or ISBN not present in the supplied context. Ticket text is treated as untrusted data in tagged blocks.
* *RAG without waste.* Seven KB sections are embedded once into pgvector; per ticket the top ≤3 chunks (similarity + category prior) plus the tone guide are sent, never the whole KB. If embeddings fail, category matching still gives the right policy.
* *Human in the loop.* Drafts are stored, editable and explicit to send; the sent message records whether it was AI-assisted.
* *Failure is a first-class state.* Backoff retries for 429/5xx/timeouts, none for permanent errors, a `FAILED` status with a visible banner and retry button, rule-based fallback priority, and a per-call `ai_runs` ledger with tokens and latency.

**Trade-offs.**
* `BackgroundTasks` instead of a queue: zero infrastructure and easy to explain, but not durable across restarts (mitigated by an admin retry that also works on stale `PROCESSING` tickets).
* In-memory WebSocket manager and login limiter: correct for one instance, would move to Redis.
* Keyword/regex guardrails are transparent and testable but blunt; they are a safety net under the model, not a replacement.
* Embedding table is tiny, so no ANN index; Postgres sequential scan is the right call at 7 rows.

**Honest gaps.** I had no Gemini key, so the live model path is verified only up to Google's auth check plus a fully scripted fake provider (106 backend tests; real PostgreSQL + pgvector verified for migrations, seed idempotency against the official BookLeaf dataset, vector search and an end-to-end WebSocket run). A seed-integrity test compares every seeded field to the source JSON. Attachments are UI-only.

**What would change in production.** Redis + worker queue with idempotent jobs and an outbox, Redis pub/sub for sockets, httpOnly cookie sessions, HNSW index and a versioned prompt registry, live evaluation in CI with override-rate monitoring (`MANUAL` sources are free quality labels), PII redaction before model calls, and OpenTelemetry tracing on the AI path.
