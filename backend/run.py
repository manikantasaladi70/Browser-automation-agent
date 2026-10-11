"""
Windows-compatible launcher for BrowseAI backend.
Run with: python run.py
"""
import sys
import asyncio

# Must be set BEFORE uvicorn imports anything asyncio-related
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # reload=True breaks ProactorEventLoop on Windows
        loop="asyncio",
    )
