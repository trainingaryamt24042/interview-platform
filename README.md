# AI Interview Platform

Domain-aware, experience-calibrated AI interviewer with **CLI** and **Web UI** that
share **one Core Engine**. LLM calls go through a router with **Gemini → OpenRouter**
fallback, including auto-discovery of working free models and the official
OpenRouter meta-routers as final safety nets.

> **🚀 Want to host this for free on a public URL?** See **[DEPLOY.md](DEPLOY.md)** for the
> step-by-step Render + Supabase walkthrough (~15 min, $0/mo).

```
┌──────────────────────┐
│      React UI        │
│  Login · Dashboard   │
│  Setup · Interview   │
│  Feedback · History  │
│  Scoreboard          │
└──────────┬───────────┘
           │ REST + cookies
┌──────────▼───────────┐    ┌──────────────────────┐
│   FastAPI (api/)     │    │     CLI (cli/)       │
│   thin controllers   │    │   thin entrypoints   │
└──────────┬───────────┘    └──────────┬───────────┘
           │                            │
           └────────────┬───────────────┘
                        │
            ┌───────────▼───────────┐
            │   Core Engine         │  ⭐ single brain
            │   (core/engine.py)    │
            └─┬──────────┬──────────┘
              │          │
   ┌──────────▼──┐  ┌────▼──────────┐
   │  Persistence│  │   LLM Router  │
   │  SQLite     │  │   retry +     │
   │  + auth     │  │   fallback    │
   └─────────────┘  └─┬─────────┬───┘
                     │         │
                ┌────▼───┐ ┌───▼────────────────────────┐
                │ Gemini │ │ OpenRouter                 │
                │ 2.0 FL │ │ • configured :free models  │
                └────────┘ │ • auto-discovered :free    │
                           │ • openrouter/free meta     │
                           │ • openrouter/auto meta     │
                           └────────────────────────────┘
```

## Features

- **Login / Register** with HttpOnly cookie auth (PBKDF2-hashed passwords).
- **Dashboard** with last grade, weak topics, strong topics, career average.
- **Setup**: domain (Data Eng, Backend, AI/ML, DevOps, Frontend, System Design),
  experience (fresher → senior), topic multi-select, custom topic, question count.
- **Chat-style Interview** with on-demand scenario questions and Ctrl/Cmd-Enter submit.
- **Feedback** report with per-topic bars, strengths, gaps, recommendations.
- **History** list of past sessions; click any to drill into per-question feedback.
- **Scoreboard** with top topics, focus areas, career average, sortable list.
- **CLI** with `interactive` and `quick` modes — calls the same engine.
- **Resilient LLM router**: 401/403 skip the provider, 404 disables the dead model
  permanently within the process, retriable errors get exponential backoff,
  meta-routers (`openrouter/free`, `openrouter/auto`) always available.
- **Persistent**: SQLite by default (zero config). Sessions, grades, per-topic
  stats, and custom topics are saved per user.

## Quickstart

### 1. Backend

```bash
git clone <repo>
cd interview_platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Put at least one of GEMINI_API_KEY or OPENROUTER_API_KEY in .env

uvicorn api.main:app --reload
# API + docs:    http://localhost:8000/docs
```

### 2. CLI (uses the same engine)

```bash
# Full mock interview
python -m cli.main interactive

# One-shot question
python -m cli.main quick \
  --domain data_engineering --experience senior \
  --topics SQL Spark --qtype scenario --show-hints
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

The Vite dev server proxies `/api/*` to `localhost:8000`. For production set
`CORS_ORIGINS` in `.env`.

### 4. Run tests

```bash
PYTHONPATH=. pytest tests/ -v   # 14 tests, ~3 seconds, no network
```

## REST API

All endpoints under `/api/v1`. Full schema at `/docs`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | — | Create account & log in |
| POST | `/auth/login` | — | Log in |
| POST | `/auth/logout` | — | Log out |
| GET | `/auth/me` | ✓ | Current user |
| GET | `/topics` | — | Domain → topic catalogue |
| POST | `/session` | optional | Start session (associated with user if logged in) |
| POST | `/generate-question` | — | Next question |
| POST | `/evaluate-answer` | — | Score & feedback |
| POST | `/generate-scenario` | — | Real-world scenario |
| POST | `/session/{id}/end` | — | Final report |
| GET | `/history/dashboard` | ✓ | Aggregate dashboard data |
| GET | `/history/grades` | ✓ | List past sessions |
| GET | `/history/grades/{id}/questions` | ✓ | Per-Q feedback |
| GET | `/history/topic-stats` | ✓ | Scoreboard data |

## How the LLM router survives model churn

OpenRouter's free model catalogue changes weekly. The router stays robust by:

1. **Configured list first** — try the model ids in `OPENROUTER_MODELS` in order.
2. **404 = dead** — when a model returns 404, it's marked dead for the rest of
   the process and never retried, so a single failure costs one attempt, not
   `LLM_RETRIES + 1`.
3. **Auto-discovery** — on first use the provider hits `GET /api/v1/models`
   and adds any `:free` model not already configured.
4. **Meta-routers always present** — `openrouter/free` (free, always picks a
   working free model) and `openrouter/auto` (paid, only fires if the account
   has credit) are appended automatically. Even if every configured model is
   dead, these will still serve the request.

There is also a unit test (`tests/test_router.py::test_404_skips_to_next_model_without_retries`)
that locks this in.

## Project layout

```
interview_platform/
├── core/                    # Shared business logic
│   ├── engine.py            # InterviewEngine (single brain)
│   ├── models.py            # Pydantic models, enums, topic catalog
│   ├── prompts.py           # Experience-aware prompt templates
│   ├── parsers.py           # LLM-output → typed model
│   ├── repository.py        # In-memory session storage
│   ├── db.py                # SQLite schema + connection
│   ├── auth.py              # User CRUD, password hashing, tokens
│   ├── history.py           # Persisted grades / topic stats
│   ├── config.py            # Env-driven settings
│   ├── logging_setup.py     # Shared logging
│   └── llm/
│       ├── base.py
│       ├── gemini.py
│       ├── openrouter.py    # 404-aware + auto-discovery + meta-routers
│       └── router.py        # Retry + fallback orchestrator
├── api/
│   ├── main.py              # FastAPI app
│   ├── routes.py            # Interview routes
│   ├── auth_routes.py       # /auth/*
│   ├── history_routes.py    # /history/*
│   ├── schemas.py
│   └── dependencies.py
├── cli/
│   └── main.py              # interactive + quick modes
├── frontend/                # React + Vite + Tailwind
│   ├── src/
│   │   ├── App.jsx
│   │   ├── lib/
│   │   │   ├── api.js
│   │   │   └── auth.jsx     # AuthProvider + useAuth hook
│   │   ├── components/      # NavBar, ChatMessage, Spinner, Badge, ScoreBar
│   │   └── pages/           # Login, Dashboard, Setup, Interview,
│   │                        # Feedback, History, HistoryDetail, Scoreboard
│   └── package.json
├── tests/
│   ├── test_parsers.py
│   ├── test_router.py
│   └── test_auth_history.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Production checklist

1. Set `AUTH_SECRET_KEY` to a strong random value.
2. Switch `DATABASE_URL` to Postgres for multi-replica deployments.
3. Set `secure=True` on the auth cookie (edit `api/auth_routes.py`) — required
   when behind HTTPS.
4. Run uvicorn with multiple workers under gunicorn or as a Kubernetes
   Deployment with HPA. Default Dockerfile uses 2 workers.
5. Build the frontend statically: `cd frontend && npm run build` and serve
   `dist/` from nginx/Caddy with TLS.
6. Set `CORS_ORIGINS` to your real frontend domain only.
7. Tail `logs/app.log` (rotating) for `LLM_USAGE` lines if you need to monitor
   provider/model health.

## Deploy to a free public host

This repo is deploy-ready with two pre-baked configs:

### Option A — Render.com (recommended, simplest)

`render.yaml` is included. **Free tier**: 750 hours/month, persistent disk,
one URL hosts both API and UI.

1. Push this repo to GitHub.
2. Go to https://dashboard.render.com/blueprints → **New Blueprint Instance**.
3. Pick the repo. Render reads `render.yaml` and creates the service.
4. In the dashboard, set the secret env vars:
   - `GEMINI_API_KEY` (or just `OPENROUTER_API_KEY`)
   - `AUTH_SECRET_KEY` is auto-generated by `generateValue: true`
5. First deploy takes ~5 min. URL appears at the top: `https://<name>.onrender.com`

Free-tier note: the service spins down after 15 min idle and cold-starts on
the next request (~30 s). For an always-on demo, pay $7/month for the
Starter plan.

### Option B — Fly.io (always-on within free limits)

`fly.toml` is included.

```bash
brew install flyctl  # or scoop/curl per https://fly.io/docs/hands-on/install-flyctl/
fly auth signup
fly launch --no-deploy            # edit `app =` first to a unique name
fly volumes create data --size 1 --region <your-region>
fly secrets set GEMINI_API_KEY=... OPENROUTER_API_KEY=... AUTH_SECRET_KEY="$(openssl rand -hex 32)"
fly deploy
```

Free allowance: 1 shared-cpu-1x VM, 256 MB RAM, 1 GB volume, 160 GB
bandwidth/month.

### Option C — Custom domain

Both Render and Fly let you add a custom domain in the dashboard. Just point
your domain's `CNAME` record at the platform's hostname; both auto-issue Let's
Encrypt TLS for free. After it's live, update `AUTH_COOKIE_SAMESITE` to
`lax` (or `none` if frontend lives elsewhere) and `AUTH_COOKIE_SECURE=1`.

### What about Vercel / Netlify / GitHub Pages?

Those are static-only and **don't run Python servers**, so they only host the
frontend. If you want to split the deploy:

- Frontend on Vercel/Netlify (free): `cd frontend && npm run build`, drop
  the `dist/` folder. Set `VITE_API_URL=https://your-api.onrender.com` in
  the build env so the frontend calls the right backend.
- Backend on Render/Fly as above. Set `AUTH_COOKIE_SAMESITE=none`,
  `AUTH_COOKIE_SECURE=1`, and add the Vercel/Netlify URL to `CORS_ORIGINS`.

The single-image Render setup (Option A) avoids cross-origin cookies entirely
and is what I'd pick for a first deploy.

## License

MIT.
