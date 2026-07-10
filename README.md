# NEXUS — AI-Powered Interview Prep Agent

Multi-turn mock interview agent built on LangGraph, Groq (structured output),
and Pinecone (RAG). Asks questions, judges answers, tracks weak areas, and
produces a final study-plan report. Multi-user with real accounts (email+
password or Google sign-in) -- each user's interview history is their own.

## Architecture

```
START -> retrieve_context -> generate_question -> await_answer (interrupt)
             ^                                          |
             |                                          v
             +------------------- judge_answer <--------+
                                       |
                          [loop until max_questions]
                                       |
                                       v
                               generate_report -> END
```

- **State**: `app/graph/state.py` — `NexusState` TypedDict, ledgers use
  `Annotated[list, add]` reducers so history/weak_areas accumulate.
- **Nodes**: `app/graph/nodes.py`
- **Checkpointing**: `PostgresSaver`, keyed by `thread_id` -- interview state
  survives process restarts, backed by the same Postgres database as user
  accounts and interview history.
- **Human-in-the-loop**: `interrupt()` in `await_answer_node` pauses the
  graph until the API resumes it with `Command(resume=answer)`.
- **Structured output**: `app/models/groq_client.py` forces Groq JSON mode
  and validates against Pydantic schemas, with a self-correcting retry.
  Calls are capped by `app/models/rate_limiter.py` (sliding window,
  configurable via `GROQ_RATE_LIMIT_CALLS`/`GROQ_RATE_LIMIT_PERIOD_SECONDS`).
- **RAG**: `app/rag/retriever.py` — hybrid retrieval, same pattern as
  RAG-Forge: Pinecone dense search + local BM25 sparse search, combined
  via Reciprocal Rank Fusion, then reranked with a cross-encoder
  (`cross-encoder/ms-marco-MiniLM-L-6-v2`) over the fused candidate pool.
- **Auth**: `app/auth/` — JWT-based sessions. Register/login with
  email+password (`app/auth/routes.py`), or Google OAuth
  (`/auth/google/login` -> `/auth/google/callback`). Every interview
  endpoint requires `Authorization: Bearer <token>` and checks that the
  requested `thread_id` actually belongs to the calling user
  (`app/api/main.py::_get_owned_interview`) -- one user can never read or
  answer another user's interview.
- **DB**: `app/db/` — SQLAlchemy models for `users` and `interviews`
  (`app/db/models.py`), same Postgres instance as the checkpointer.

## Setup

```bash
cp .env.example .env
```

Fill in `.env`:
- `GROQ_API_KEY`, `PINECONE_API_KEY` -- required
- `DATABASE_URL` -- your Postgres connection string
- `JWT_SECRET_KEY` -- generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- optional, leave blank to
  disable Google login (email+password still works standalone). Get these
  from https://console.cloud.google.com/apis/credentials -- set the
  authorized redirect URI to match `GOOGLE_REDIRECT_URI`.

```bash
pip install -r requirements.txt
```

Seed the Pinecone index with starter prep material (System Design, Python
DSA, Behavioral, ML, SQL):

```bash
python -m scripts.seed_pinecone
```

Re-run this any time you edit `app/rag/seed_data.py` — upserts are
idempotent by `id`.

## Run locally

Needs a running Postgres instance matching `DATABASE_URL`. Tables (users,
interviews, LangGraph checkpoints) are created automatically on first run
-- no manual migration step.

```bash
uvicorn app.api.main:app --reload
```

Open `http://localhost:8000` -- you'll land on a login screen. Register
with email+password, or use "Sign in with Google" if configured.

## Run with Docker

```bash
docker compose up --build
```

This starts Postgres (`db` service) and the app (`nexus` service)
together, with a named volume for Postgres data so it survives restarts.

## Deploying to Render

`render.yaml` in this repo defines the web service as a Blueprint, but a
few things need a real human (you) because they involve secrets, external
accounts, or judgment calls Render can't make for you:

**1. Pick a Postgres provider -- do NOT use Render's free Postgres.**
Render's free Postgres tier auto-deletes the entire database 30 days
after creation, no warning beyond an email, no way to opt out short of
paying. That would silently wipe every user account and interview when it
happens. Two real options:
- **[Neon](https://neon.tech)** -- free tier that doesn't expire, has
  built-in connection pooling. Simplest choice for this project's scale.
- **Render's paid Postgres** (Starter, ~$7/mo) -- if you'd rather keep
  everything on one platform.

Either way: create the database, copy its connection string
(`postgresql://...`), you'll paste it into Render in step 4.

**2. Get a Google OAuth client (only if you want Google sign-in).**
https://console.cloud.google.com/apis/credentials -> Create Credentials ->
OAuth client ID -> Web application. Leave the redirect URI blank for now
-- you'll add your real Render URL once you have it (step 5). Skip this
entirely if email+password login is enough; the app works without it.

**3. Push this repo to GitHub**, then in the Render dashboard: New ->
Blueprint -> connect the repo. Render reads `render.yaml` and creates the
web service.

**4. Fill in the secrets Render can't generate itself**, in the service's
Environment tab:
- `DATABASE_URL` -- the connection string from step 1
- `GROQ_API_KEY`, `PINECONE_API_KEY` -- your existing keys (rotate them
  first if they were ever shared/pasted anywhere outside your own machine)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- from step 2, if using Google login

`JWT_SECRET_KEY` is already handled -- `render.yaml` has Render generate
it randomly for you.

**5. Set the URL-dependent variables once you know your Render URL**
(it'll be `https://nexus-xxxx.onrender.com` or similar):
- `GOOGLE_REDIRECT_URI` = `https://<your-render-url>/auth/google/callback`
- `FRONTEND_URL` = `https://<your-render-url>`
- Also go back to Google Cloud Console and add that same redirect URI to
  the OAuth client from step 2 -- Google rejects the callback otherwise.

**6. Seed Pinecone once, pointed at your production database.** Run
locally with production env vars:
```bash
DATABASE_URL="<your production connection string>" \
PINECONE_API_KEY="..." \
python -m scripts.seed_pinecone
```
This also runs fine as a one-off Render Shell command from the dashboard
if you'd rather not export secrets locally.

**What you do NOT need to do manually:** create the `users`/`interviews`/
`corpus_chunks`/checkpoint tables (created automatically on first request),
write a Dockerfile (already in the repo), or configure HTTPS (Render
handles that automatically).

**Free tier reality check:** Render's free web service spins down after
15 minutes of no traffic and takes ~30-60s to cold-start on the next
request. Fine for 5-10 people who know that going in; if you want it to
feel instant when you demo it live to a recruiter, the $7/mo Starter tier
removes the spin-down.

## API

All endpoints except `/auth/register`, `/auth/login`, and the Google OAuth
routes require `Authorization: Bearer <token>` (obtained from
`/auth/register` or `/auth/login`, or via the Google flow). Requests are
rate-limited per client IP (`/start_interview`: 10/min, `/submit_answer`:
20/min, `/get_report`: 30/min), and Groq calls themselves are capped
separately (default 20 calls/60s) to control API spend regardless of
which client is hitting the server.

### `POST /auth/register`
```json
{"email": "you@example.com", "password": "..."}
```
→ `{"access_token": "...", "token_type": "bearer"}`

### `POST /auth/login`
Same request/response shape as register.

### `GET /auth/google/login`
Redirects to Google's consent screen. On success, redirects back to
`FRONTEND_URL/#token=...` -- the frontend JS picks the token up from the
URL fragment.

### `GET /auth/me`
→ `{"id": "...", "email": "..."}`

### `POST /start_interview`
```json
{"topic": "System Design", "difficulty": "medium", "max_questions": 5}
```
→ `{"thread_id": "...", "question_number": 1, "question": "..."}`

### `POST /submit_answer`
```json
{"thread_id": "...", "answer": "..."}
```
→ next question, or `{"is_complete": true}` when done.

### `GET /get_report?thread_id=...`
→ final structured report once the interview is complete. 404 if the
thread doesn't exist or doesn't belong to you.

### `GET /interviews`
→ your own interview history: `[{"thread_id", "topic", "difficulty", "is_complete", "created_at"}, ...]`

## Loading prep material into Pinecone

Add chunks to `app/rag/seed_data.py` (or write your own loader) using
`app.rag.retriever.upsert_material()` with chunks of the form:
```python
{"id": "sysdesign-001", "text": "...", "topic": "System Design"}
```
Then run `python -m scripts.seed_pinecone`. This writes to both Pinecone
(dense) and Postgres's `corpus_chunks` table (BM25 sparse) -- both need
to stay in sync, so always go through `upsert_material()` rather than
writing to Pinecone directly.

## Status / Next steps

- [x] Load starter prep material into Pinecone index (`scripts/seed_pinecone.py`)
- [x] Persistent `PostgresSaver` checkpointer, connection-pooled for resilience
- [x] Real multi-user auth: email+password and Google OAuth, JWT sessions
- [x] Per-user interview history with ownership checks (`/interviews`)
- [x] Rate limiting (per-IP on endpoints, per-process on Groq calls)
- [x] Hybrid retrieval: Pinecone dense + Postgres-backed BM25 sparse + RRF fusion + cross-encoder reranking
- [x] Deployment-ready: `/health` endpoint, error logging, `render.yaml` blueprint, no local-disk dependencies
- [ ] Expand seed material beyond the starter set for topics you'll actually be asked about
- [ ] Refresh tokens / logout-everywhere (currently a single long-lived access token, no revocation list)
- [ ] Password reset flow (not needed if you're personally inviting all 5-10 users)
