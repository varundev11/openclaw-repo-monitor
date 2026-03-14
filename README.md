# openclaw_monitor

Lightweight monitor for the openclaw/openclaw repository.

Features
- Background snapshot every 30 minutes (kept as latest 3 snapshots, ~1.5 hours sliding window)
- Stores compact JSON snapshots in a GitHub secret gist (PRs, issues, recent commits, reviewers, CI status, comments excerpts)
- FastAPI public endpoints:
  - GET /snapshots
  - GET /snapshots/{ts}
  - GET /report/latest
  - GET /wakeup
  - HEAD /wakeup
- Local CLI to force snapshot or run analysis

Usage
1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set your `GIST_TOKEN` (GitHub Personal Access Token with gist permissions)
3. Run: `uvicorn app:app --host 0.0.0.0 --port 8080`
4. Snapshots stored in a GitHub secret gist (automatically created if not exists)

Deployment on Render
1. Create a Render account at https://render.com and connect your GitHub account.
2. Fork or push this repository to your GitHub account.
3. In the Render dashboard, click "New +" and select "Web Service".
4. Connect your GitHub repository by selecting the repo you pushed.
5. Configure the service:
   - Name: Choose a name for your service (e.g., openclaw-monitor)
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
6. Add environment variables:
   - GIST_TOKEN: Your GitHub personal access token with gist permissions
7. Click "Create Web Service".
8. Once deployed, your app will be available at the provided URL (e.g., https://your-service.onrender.com).
9. The service will automatically start collecting snapshots every 30 minutes.
10. Use the /wakeup endpoints to keep the service awake if needed (Render free tier sleeps after inactivity).

Deployment
- Dockerfile included.

Security
- The service is intentionally minimal and exposes a public API. Protect the token and hosting environment appropriately.
- Snapshots are stored in a secret GitHub gist, visible only to you.
- The monitored repository is public, so no additional token is needed for reading repo data.
