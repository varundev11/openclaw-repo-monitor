import os
import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from collector import MonitorCollector

load_dotenv()

app = FastAPI(title="openclaw-repo-monitor")
collector = MonitorCollector()

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
    content = collector.get_snapshot_content(ts)
    if not content:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return json.loads(content)

@app.get("/report/latest")
def report_latest():
    snap = collector.load_latest()
    if not snap:
        raise HTTPException(status_code=404, detail="no snapshots available")
    report = collector.summarize_snapshot(snap)
    return report

@app.post("/snapshots/force")
async def force_snapshot():
    asyncio.create_task(collector.collect_and_prune())
    return {"status": "collection triggered"}

@app.get("/wakeup")
async def wakeup():
    return {"status": "awake", "message": "This server is awake."}

@app.head("/wakeup")
async def wakeup_head():
    return
