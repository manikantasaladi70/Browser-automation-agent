import asyncio
import base64
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

# Fix Windows event loop for Playwright BEFORE uvicorn touches anything
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from agent import BrowserAgent
from database import Database

load_dotenv()

browser_instance: Optional[Browser] = None
playwright_instance = None
db: Optional[Database] = None

# ── Try to connect to your existing Chrome via remote debugging ──────────────
# Run this in CMD first (once), then keep that Chrome open:
#   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-agent-profile"
CHROME_DEBUG_PORT = 9222
CHROME_DEBUG_URL  = f"http://localhost:{CHROME_DEBUG_PORT}"


async def try_connect_existing_chrome(pw) -> Optional[Browser]:
    """Connect to already-running Chrome with --remote-debugging-port=9222"""
    try:
        browser = await pw.chromium.connect_over_cdp(CHROME_DEBUG_URL)
        print(f"✅ Connected to existing Chrome at {CHROME_DEBUG_URL}")
        return browser
    except Exception as e:
        print(f"⚠️  Could not connect to existing Chrome ({e})")
        print("   Falling back to launching a new browser...")
        return None


async def launch_new_browser(pw) -> Browser:
    """Launch a fresh Chromium if existing Chrome not available"""
    return await pw.chromium.launch(
        headless=False,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--start-maximized",
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global browser_instance, playwright_instance, db

    playwright_instance = await async_playwright().start()

    # Try existing Chrome first, fall back to new browser
    browser_instance = await try_connect_existing_chrome(playwright_instance)
    if browser_instance is None:
        browser_instance = await launch_new_browser(playwright_instance)

    db = Database()
    print("✅ Browser ready and DB initialized.")
    yield

    # Only close if we launched it ourselves (not if we connected to user's Chrome)
    try:
        await browser_instance.close()
    except Exception:
        pass
    await playwright_instance.stop()
    print("Browser closed.")


app = FastAPI(title="BrowseAI Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str
    url: Optional[str] = None


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, task_id: str, ws: WebSocket):
        await ws.accept()
        self.active[task_id] = ws

    def disconnect(self, task_id: str):
        self.active.pop(task_id, None)

    async def send(self, task_id: str, data: dict):
        ws = self.active.get(task_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(task_id)


manager = ConnectionManager()


@app.get("/health")
async def health():
    return {"status": "ok", "browser": browser_instance is not None}


@app.post("/tasks")
async def create_task(req: TaskRequest):
    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "task": req.task,
        "url": req.url or "",
        "status": "queued",
        "created_at": time.time(),
        "steps": [],
        "result": None,
        "screenshot": None,
    }
    await db.save_task(task_data)
    asyncio.create_task(run_agent_task(task_id, req.task, req.url))
    return {"task_id": task_id}


async def run_agent_task(task_id: str, task: str, url: Optional[str]):
    context: BrowserContext = None
    try:
        # If connected to existing Chrome, use its existing context (keeps sessions/cookies)
        # Otherwise create a fresh context
        existing_contexts = browser_instance.contexts
        if existing_contexts:
            context = existing_contexts[0]  # reuse the existing logged-in context
            page: Page = await context.new_page()
            print("✅ Reusing existing Chrome context (sessions preserved)")
        else:
            context = await browser_instance.new_context(
                viewport={"width": 1366, "height": 768},
                java_script_enabled=True,
                accept_downloads=True,
            )
            page: Page = await context.new_page()

        # Anti-detection (wrapped in try — may fail on existing context)
        try:
            await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        except Exception:
            pass

        agent = BrowserAgent(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            page=page,
            context=context,
            task_id=task_id,
            manager=manager,
            db=db,
        )

        await db.update_task(task_id, {"status": "running"})

        # Wait for WebSocket to connect before sending any events
        await asyncio.sleep(1.5)
        await manager.send(task_id, {"type": "status", "status": "running"})

        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.5)

        result = await agent.run(task)

        screenshot_b64 = await _take_screenshot(agent.page)
        await db.update_task(task_id, {
            "status": "done",
            "result": result,
            "screenshot": screenshot_b64,
        })
        await manager.send(task_id, {
            "type": "done",
            "result": result,
            "screenshot": screenshot_b64,
        })

    except Exception as e:
        err = str(e)
        await db.update_task(task_id, {"status": "error", "result": err})
        await manager.send(task_id, {"type": "error", "message": err})
    finally:
        # Only close the page, NOT the context (so sessions stay alive)
        try:
            await page.close()
        except Exception:
            pass


async def _take_screenshot(page: Page) -> str:
    try:
        buf = await page.screenshot(type="jpeg", quality=80, full_page=False)
        return base64.b64encode(buf).decode()
    except Exception:
        return ""


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id)


@app.get("/tasks")
async def list_tasks():
    tasks = await db.list_tasks()
    return {"tasks": tasks}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    await db.delete_task(task_id)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, loop="asyncio")