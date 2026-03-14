# openclaw_monitor

Lightweight monitor for the openclaw/openclaw repository.

Features
- Background snapshot every 30 minutes (kept as latest 3 snapshots, ~1.5 hours sliding window)
- Stores compact JSON snapshots (PRs, issues, recent commits, reviewers, CI status, comments excerpts)
- FastAPI public endpoints:
  - GET /snapshots
  - GET /snapshots/{ts}
  - GET /report/latest
- Local CLI to force snapshot or run analysis

Usage
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variable: `GITHUB_TOKEN` (token with repo scope if monitoring private repo; public-only for public)
3. Run: `uvicorn app:app --host 0.0.0.0 --port 8080`
4. Snapshots stored at `workspace/projects/openclaw_monitor/snapshots/`

Deployment
- Dockerfile included.

Security
- The service is intentionally minimal and exposes a public API. Protect the token and hosting environment appropriately.
