# Deploying the live demo

The whole app ships as **one container**: FastAPI serves the API (under `/api`)
and the built React dashboard (at `/`) from a single process. So you deploy
**one free service** and get **one clickable URL** for your CV — no CORS, no
second deploy, **no API key** (the agent runs in deterministic heuristic mode),
and the sample statements are **seeded on first boot** so the demo is never
empty.

## Try it locally first (one command)

```bash
docker compose up --build
# open http://localhost:8000  → dashboard, pre-seeded with 67 transactions
```

## Deploy to Render (free, recommended)

Render reads the repo `Dockerfile` and `render.yaml` for you.

1. **Push the repo to GitHub** (one-time):
   ```bash
   git init && git add -A && git commit -m "Personal Finance Agent"
   git branch -M main
   git remote add origin https://github.com/<you>/finance-agent.git
   git push -u origin main
   ```
2. Go to **render.com** → sign in with GitHub → **New → Blueprint**.
3. Pick the repo. Render detects `render.yaml`, creates a free Docker web
   service, builds, and deploys. First build ~3–5 min.
4. You get a URL like `https://finance-agent.onrender.com`. That's your CV link.

**Free-tier notes (set expectations on your CV):**
- The service **sleeps after ~15 min idle**; the first hit then takes ~30–60s
  to wake. Fine for a demo — just mention "may take a moment to wake" near the
  link, or ping it before showing it to someone.
- Storage is **ephemeral**: on restart the DB resets, but seed-on-boot
  repopulates the sample data automatically, so the demo always looks right.
- To enable the real LLM path, add `ANTHROPIC_API_KEY` in the Render dashboard
  (Environment tab). Optional — everything works without it.

## Alternative: Fly.io

```bash
fly launch --dockerfile Dockerfile --now   # accept defaults; pick the free plan
```
Fly keeps the machine warm longer than Render's free tier (fewer cold starts)
but requires a card on file.

## Putting it on your CV

```
Live demo: https://finance-agent.onrender.com   (heuristic mode, no key needed)
Code:      https://github.com/<you>/finance-agent
```

Tip: also record a 60–90s screen capture of the full flow (upload → reconcile →
chat → charts) and link it too — a video never cold-starts and survives if you
ever take the host down.
