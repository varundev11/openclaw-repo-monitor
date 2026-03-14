#!/usr/bin/env python3
import os
import asyncio
from collector import MonitorCollector

async def main():
    SNAP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'snapshots')
    os.makedirs(SNAP_DIR, exist_ok=True)
    c = MonitorCollector(snapshot_dir=SNAP_DIR)
    await c.collect_and_prune()

if __name__ == '__main__':
    asyncio.run(main())
