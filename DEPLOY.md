# Deploy to a free public URL (Render + Supabase)

This walks you through deploying the platform to a free subdomain like
`https://interview-platform-XXXX.onrender.com` that anyone on the internet
can use. Total time: **~15 minutes**, **cost: $0/month**.

The stack:

| Piece | Where | Free tier |
|---|---|---|
| API + UI (one container) | Render web service | 750 instance hours/month, sleeps after 15 min idle |
| Postgres database | Supabase | 500 MB, no expiry, dedicated free project |
| HTTPS certificate | Render auto-issues Let's Encrypt | Forever |
| LLM | Gemini 2.0 Flash Lite (primary) + OpenRouter free models (fallback) | Forever |

> **Cold start expectation**: the first visitor after 15 min of inactivity
> waits ~30 seconds while Render spins the container back up. After that
> it's normal speed. For a portfolio/demo this is fine.

---

## Step 1 — Get a free Postgres from Supabase (3 min)

1. Go to **https://supabase.com** → **Start your project** → sign up with GitHub
2. Click **New project**:
   - **Name**: `interview-platform`
   - **Database Password**: pick a strong one — copy it somewhere safe, you'll need it in step 4 below
   - **Region**: pick the one closest to you
   - Click **Create new project**
3. Wait ~1 minute for provisioning. The page reloads when ready.
4. **Click the green "Connect" button at the top of the page** (in the header bar, next to the project name).
5. A dialog opens with several tabs. Click **"Transaction pooler"** — this is the one our app needs.
6. Copy the connection string. It looks like this:
   ```
   postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
7. **In a text editor**, replace `[YOUR-PASSWORD]` with the actual password you set in step 2, AND append `?sslmode=require` at the end. The final URL should look like:
   ```
   postgresql://postgres.xxxxxxxxxxxx:YourRealPassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```

Save this final URL — you'll paste it into Render in step 4.

> **Why transaction pooler (port 6543)?** It's designed for many short-lived
> connections, which is exactly how Render's free workers behave. The direct
> connection (port 5432) would hit the free-tier 60-connection cap quickly.

> **Can't find the Connect button?** Wait until provisioning finishes (the
> page will reload from a setup wizard to the actual dashboard). If still
> missing, alternate path: bottom-left **Settings ⚙** → **Database** →
> **Connection string** section → **Transaction pooler** tab.

---

## Step 2 — Get the LLM API keys (3 min)

Either or both:

**Gemini (free, recommended)**
1. https://aistudio.google.com/app/apikey
2. **Create API key** → pick "Create API key in new project" if asked
3. Copy the key (starts with `AIza...`)

**OpenRouter (free, fallback)**
1. https://openrouter.ai/keys
2. Sign up → **Create Key** → name it anything
3. Copy the key (starts with `sk-or-v1-...`)

---

## Step 3 — Push to GitHub (3 min)

In a terminal **inside** the `interview_platform` folder:

```bash
git init
git add .
git commit -m "Initial commit"
```

Create a new repo at https://github.com/new (any name, public is simpler).
**Don't** check any "Initialize with…" boxes.

GitHub then shows you the push commands — run them:

```bash
git remote add origin https://github.com/YOUR_USERNAME/interview-platform.git
git branch -M main
git push -u origin main
```

When asked for a password, use a Personal Access Token from
https://github.com/settings/tokens (scope: `repo`).

---

## Step 4 — Deploy on Render (5 min)

1. Sign up at **https://render.com** (use **Sign up with GitHub** — auto-grants repo access)
2. Top right: **New +** → **Blueprint**
3. Pick your `interview-platform` repo. If it doesn't show up, click
   **Configure account** → grant access to that repo → come back.
4. Render reads `render.yaml` and shows: *"1 service will be created"*. Give the blueprint instance a name (anything) → **Apply**
5. The **first deploy will fail** with a "Database connection error" — that's expected because we haven't pasted the secrets yet. **Don't panic.**
6. Click into the service → **Environment** tab → fill in:
   - `DATABASE_URL` → paste your Supabase URL from Step 1
   - `GEMINI_API_KEY` → your Gemini key
   - `OPENROUTER_API_KEY` → your OpenRouter key (or leave blank if not using)
7. **Save Changes** — this triggers a redeploy
8. Watch the logs: you should see
   ```
   DB schema ready (backend=postgres)
   API starting on 0.0.0.0:8000 (gemini=True, ...)
   ```
9. When the badge at the top says **Live**, click the URL: `https://interview-platform-XXXX.onrender.com`

---

## Step 5 — Verify (2 min)

Open these three URLs:

| URL | Expected |
|---|---|
| `/` | Login screen |
| `/api/v1/health` | `{"status":"ok"}` |
| `/docs` | Swagger UI |

Then register a test user and complete one short interview:

1. Login screen → **Register** tab → username `test` / password `test1234`
2. Pick a domain, level, 2 questions, **Start Interview**
3. Answer both, hit **End & Score**
4. You should land on the report screen
5. Click **History** in the nav — your session should appear
6. Click the session — you should see per-question feedback

**Persistence test**: in the Render dashboard, click **Manual Deploy** →
**Deploy latest commit**. Wait ~3 min. Refresh the site. Your test user and
their interview history should still be there. ✅ That confirms Postgres is
working.

---

## Step 6 — Share

Your URL is `https://interview-platform-XXXX.onrender.com`. Send it to anyone.
They'll see the cold-start delay on first visit if no one has used it in 15+ minutes; after that it's instant for the duration of their session.

---

## Updating later

```bash
git add .
git commit -m "what changed"
git push
```

Render's `autoDeploy: true` redeploys on every push to `main`. Your
Postgres data keeps living in Supabase across all redeploys.

---

## Optional: keep the service warm (~free uptime monitor)

If 30-second cold starts annoy you, set up a free pinger that hits the
health endpoint every 5 minutes:

1. https://uptimerobot.com → sign up free
2. **Add New Monitor** → **HTTP(s)** → URL: `https://your-app.onrender.com/api/v1/health`
3. Interval: 5 minutes → **Create Monitor**

Render's free tier is 750 instance-hours/month. A single service running
24/7 = 720 hours. The 30-hour buffer absorbs the occasional minute of
double-running during deploys.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Database connection error" in logs | `DATABASE_URL` not set or wrong | Re-paste from Supabase, check `[YOUR-PASSWORD]` was replaced |
| "could not translate host name" | Using the old direct-connection URL | Use the **Connection Pooling** URL on port `6543` instead |
| Login works, dashboard returns 401 | Cookie `Secure` mismatch | In Render env, ensure `AUTH_COOKIE_SECURE=1` and `AUTH_COOKIE_SAMESITE=lax` |
| All LLM calls return 502 | API keys wrong / not set | Re-paste in Render Environment tab |
| Build fails on `npm install` | Likely a flaky Render build node | **Manual Deploy** → **Clear build cache & deploy** |
| `psycopg.OperationalError: SSL connection has been closed` | Supabase pooler short-circuits idle conns | This is fine — the connection is re-opened on next request. If it bothers you, restart the service. |

---

## Migrating off the free tier later

When you outgrow the free tier:

- **Render**: upgrade the service to **Starter** ($7/mo) → no more cold starts. No code changes needed.
- **Supabase**: Pro tier is $25/mo and gives you 8 GB. Or migrate to a self-managed Postgres just by changing `DATABASE_URL`.

Nothing about your code or data needs to change.
