import os
import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from collector import MonitorCollector

SNAP_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

app = FastAPI(title="openclaw-repo-monitor")
collector = MonitorCollector(snapshot_dir=SNAP_DIR)

@app.on_event("startup")
async def startup_event():
    # start background snapshot task
    asyncio.create_task(collector.schedule_loop(interval_minutes=30))

@app.get("/snapshots")
def list_snapshots():
    snaps = collector.list_snapshots()
    return {"snapshots": snaps}

@app.get("/snapshots/{ts}")
def get_snapshot(ts: str):
    path = collector.snapshot_path(ts)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="snapshot not found")
    with open(path, 'r') as f:
        return json.load(f)

@app.get("/report/latest")
def report_latest():
    snap = collector.load_latest()
    if not snap:
        raise HTTPException(status_code=404, detail="no snapshots available")
    report = collector.summarize_snapshot(snap)
    return report
