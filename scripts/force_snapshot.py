#!/usr/bin/env python3
import os
import asyncio
from collector import MonitorCollector

async def main():
    c = MonitorCollector()
    await c.collect_and_prune()

if __name__ == '__main__':
    asyncio.run(main())
