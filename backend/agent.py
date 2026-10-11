import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Optional

from groq import AsyncGroq
from playwright.async_api import Page, BrowserContext

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are BrowseAI, an expert browser automation agent controlling a real Chromium browser.

You receive: current URL, page title, interactive elements, forms, and a screenshot.
You output: a JSON array of actions to fully complete the task end-to-end.

## Actions available:
- {"action": "navigate", "url": "https://..."}
- {"action": "click", "selector": "CSS selector", "description": "what"}
- {"action": "click_text", "text": "exact visible button/link text", "description": "what"}
- {"action": "type", "selector": "CSS selector", "text": "...", "clear": true}
- {"action": "press", "key": "Enter"}
- {"action": "wait_for", "selector": "CSS selector", "timeout": 15000}
- {"action": "wait", "ms": 2000}
- {"action": "scroll", "direction": "down", "amount": 500}
- {"action": "extract", "selector": "CSS selector", "description": "what data"}
- {"action": "extract_text", "description": "all visible text"}
- {"action": "screenshot", "description": "capture current state"}
- {"action": "save_screenshot", "filename": "result.png", "description": "save screenshot to disk"}
- {"action": "new_tab", "url": "https://...", "description": "open in new tab"}
- {"action": "switch_tab", "index": 0, "description": "switch to tab by index"}
- {"action": "upload_file", "selector": "input[type=file]", "filepath": "screenshots/file.png"}
- {"action": "select", "selector": "select", "value": "option value"}
- {"action": "fill_google_form", "fields": {"DATE": "2025-06-28", "TIME": "15:45", "NAME": "...", "EMPLOYEE ID": "...", "DOMAIN": "AI"}, "description": "fill all Google Form fields at once"}
- {"action": "hover", "selector": "CSS selector"}
- {"action": "wait_for_login", "url_contains": "chatgpt.com/c/", "description": "wait for user to log in"}
- {"action": "done", "result": "clear summary of everything accomplished"}
- {"action": "error", "message": "why it failed"}

## CRITICAL rules:
1. Return ONLY a valid JSON array. No markdown, no explanation, no code fences.
2. NEVER use nth-child with colons like nth-child(1:5) — INVALID CSS.
3. Use click_text for buttons/links — more reliable than CSS selectors.
4. For ChatGPT: use selector "div[contenteditable='true']" or "#prompt-textarea" for input.
5. For WhatsApp Web: search box is "div[contenteditable][data-tab='3']", attach is "div[title='Attach']".
6. Always wait after navigation: {"action": "wait", "ms": 2000}
7. For login pages (ChatGPT/WhatsApp): immediately use wait_for_login action — do NOT try to automate login. The user will log in manually and the agent resumes automatically.
8. After sending a message in ChatGPT, use wait_for to wait for response: {"action": "wait_for", "selector": "[data-message-author-role='assistant']", "timeout": 60000}
9. To send image on WhatsApp: click attach → upload_file with the saved screenshot path → click send button.
10. save_screenshot saves the current page as an image file you can later upload.
11. Always end with "done" describing exactly what was accomplished.
12. Max 20 actions.
13. For Google Forms: ALWAYS use fill_google_form action — it fills all fields reliably in one step. Never try to click individual form fields with click/type actions on Google Forms.

### Google Form filling:
[
  {"action": "navigate", "url": "https://docs.google.com/forms/..."},
  {"action": "wait", "ms": 3000},
  {"action": "fill_google_form", "fields": {"DATE": "2025-06-28", "TIME": "15:45", "NAME": "Saladi Manikanta", "EMPLOYEE ID": "TEN/AI/810186", "DOMAIN": "AI"}, "description": "fill attendance form"},
  {"action": "click_text", "text": "Submit", "description": "submit the form"},
  {"action": "wait", "ms": 2000},
  {"action": "save_screenshot", "filename": "form_submitted.png", "description": "confirmation screenshot"},
  {"action": "done", "result": "Attendance form filled and submitted successfully"}
]

## Common task patterns:

### ChatGPT → Screenshot → WhatsApp:
[
  {"action": "navigate", "url": "https://chatgpt.com"},
  {"action": "wait_for_login", "url_contains": "chatgpt.com", "description": "wait for user to log in to ChatGPT"},
  {"action": "click", "selector": "div[contenteditable='true']", "description": "click chat input"},
  {"action": "type", "selector": "div[contenteditable='true']", "text": "Give me a 7 day diet plan", "clear": false},
  {"action": "press", "key": "Enter"},
  {"action": "wait_for", "selector": "[data-message-author-role='assistant']", "timeout": 60000},
  {"action": "wait", "ms": 5000},
  {"action": "save_screenshot", "filename": "chatgpt_result.png", "description": "save ChatGPT response"},
  {"action": "new_tab", "url": "https://web.whatsapp.com", "description": "open WhatsApp"},
  {"action": "wait_for_login", "url_contains": "web.whatsapp.com", "description": "wait for WhatsApp QR scan"},
  {"action": "click", "selector": "div[contenteditable][data-tab='3']", "description": "search box"},
  {"action": "type", "selector": "div[contenteditable][data-tab='3']", "text": "ContactName", "clear": false},
  {"action": "wait", "ms": 1500},
  {"action": "click", "selector": "span[title='ContactName']", "description": "select contact"},
  {"action": "click", "selector": "div[title='Attach']", "description": "attach button"},
  {"action": "upload_file", "selector": "input[type='file']", "filepath": "screenshots/chatgpt_result.png"},
  {"action": "wait", "ms": 1500},
  {"action": "click_text", "text": "Send", "description": "send image"},
  {"action": "done", "result": "Diet plan screenshot sent on WhatsApp"}
]

### Form filling:
[
  {"action": "navigate", "url": "https://..."},
  {"action": "wait", "ms": 1500},
  {"action": "type", "selector": "input[name='name']", "text": "John Doe", "clear": true},
  {"action": "type", "selector": "input[name='email']", "text": "john@email.com", "clear": true},
  {"action": "click_text", "text": "Submit", "description": "submit form"},
  {"action": "done", "result": "Form filled and submitted"}
]"""

VERIFY_PROMPT = """Verify if browser task was completed. Reply ONLY with JSON:
{"success": true/false, "summary": "what was accomplished", "issues": "any problems"}"""


class BrowserAgent:
    def __init__(self, groq_api_key: str, page: Page, context: BrowserContext, task_id: str, manager, db):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.page = page
        self.context = context
        self.task_id = task_id
        self.manager = manager
        self.db = db
        self.steps = []
        self.max_retries = 2
        self.pages = [page]  # track all tabs

    async def emit(self, event: dict):
        await self.manager.send(self.task_id, event)
        self.steps.append(event)
        await self.db.append_step(self.task_id, event)

    async def get_page_context(self) -> dict:
        try:
            title = await self.page.title()
            url = self.page.url
            dom_summary = await self.page.evaluate("""() => {
                const interactable = [];
                const els = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [contenteditable]');
                els.forEach((el, i) => {
                    if (i > 50) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) return;
                    interactable.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || el.getAttribute('contenteditable') || '',
                        text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.getAttribute('data-placeholder') || '').slice(0, 80).trim(),
                        id: el.id || '',
                        name: el.name || '',
                        title: el.title || '',
                        class: (el.className || '').toString().slice(0, 50),
                    });
                });
                return {
                    title: document.title,
                    interactable: interactable.slice(0, 40),
                    bodyText: document.body?.innerText?.slice(0, 1000) || '',
                    forms: Array.from(document.querySelectorAll('form')).map(f => ({
                        inputs: Array.from(f.querySelectorAll('input,select,textarea')).map(i => ({
                            name: i.name, type: i.type, placeholder: i.placeholder, id: i.id
                        }))
                    })).slice(0, 3)
                };
            }""")
            screenshot_buf = await self.page.screenshot(type="jpeg", quality=65, full_page=False)
            screenshot_b64 = base64.b64encode(screenshot_buf).decode()
            return {"title": title, "url": url, "dom": dom_summary, "screenshot": screenshot_b64}
        except Exception as e:
            return {"title": "", "url": self.page.url, "dom": {}, "screenshot": "", "error": str(e)}

    async def plan(self, task: str, context: dict, retry_hint: str = "") -> list:
        ctx_text = f"""Current URL: {context['url']}
Page title: {context['title']}
Open tabs: {len(self.pages)}
Forms: {json.dumps(context['dom'].get('forms', []))}
Elements: {json.dumps(context['dom'].get('interactable', []))}
Page text (first 800 chars): {context['dom'].get('bodyText', '')[:800]}
{f'PREVIOUS ATTEMPT FAILED: {retry_hint}' if retry_hint else ''}

TASK: {task}"""

        messages = [{"role": "user", "content": [{"type": "text", "text": ctx_text}]}]
        if context.get("screenshot"):
            messages[0]["content"].insert(0, {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{context['screenshot']}"}
            })

        response = await self.client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=2000,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        try:
            actions = json.loads(raw)
            if not isinstance(actions, list):
                actions = [{"action": "error", "message": "Invalid plan"}]
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            actions = json.loads(match.group()) if match else [{"action": "error", "message": f"Parse failed: {raw[:200]}"}]
        return actions

    async def _screenshot(self) -> str:
        try:
            buf = await self.page.screenshot(type="jpeg", quality=72, full_page=False)
            return base64.b64encode(buf).decode()
        except Exception:
            return ""

    async def execute_action(self, action: dict) -> Optional[str]:
        act = action.get("action")

        if act == "navigate":
            url = action["url"]
            await self.emit({"type": "step", "action": "navigate", "description": f"Navigating to {url}"})
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"Loaded: {url}"})

        elif act == "new_tab":
            url = action.get("url", "about:blank")
            desc = action.get("description", url)
            await self.emit({"type": "step", "action": "navigate", "description": f"Opening new tab: {desc}"})
            new_page = await self.context.new_page()
            self.pages.append(new_page)
            self.page = new_page
            await new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"New tab: {url}"})

        elif act == "switch_tab":
            idx = action.get("index", 0)
            if 0 <= idx < len(self.pages):
                self.page = self.pages[idx]
                await self.page.bring_to_front()
                ss = await self._screenshot()
                await self.emit({"type": "screenshot", "screenshot": ss, "description": f"Switched to tab {idx}"})

        elif act == "click":
            sel = action["selector"]
            desc = action.get("description", sel)
            await self.emit({"type": "step", "action": "click", "description": f"Clicking: {desc}"})
            try:
                await self.page.wait_for_selector(sel, timeout=8000)
                await self.page.click(sel, timeout=8000)
            except Exception:
                await self.page.evaluate(f"document.querySelector('{sel.replace(chr(39), chr(92)+chr(39))}')?.click()")
            await asyncio.sleep(1)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"After: {desc}"})

        elif act == "click_text":
            text = action["text"]
            desc = action.get("description", text)
            await self.emit({"type": "step", "action": "click", "description": f"Clicking '{text}'"})
            clicked = False
            for sel in [
                f"text={text}",
                f"button:has-text('{text}')",
                f"a:has-text('{text}')",
                f"[aria-label='{text}']",
                f"input[value='{text}']",
                f"span:has-text('{text}')",
            ]:
                try:
                    await self.page.click(sel, timeout=4000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                await self.page.evaluate(f"""
                    const t = {json.dumps(text)};
                    const els = document.querySelectorAll('button,a,input[type=submit],[role=button],div[role=button],span');
                    for (const el of els) {{
                        if ((el.innerText||el.value||el.getAttribute('aria-label')||'').trim().toLowerCase().includes(t.toLowerCase())) {{
                            el.click(); break;
                        }}
                    }}
                """)
            await asyncio.sleep(1)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"After clicking '{text}'"})

        elif act == "type":
            sel = action["selector"]
            text = action["text"]
            clear = action.get("clear", True)
            await self.emit({"type": "step", "action": "type", "description": f"Typing: '{text[:40]}'"})
            try:
                await self.page.wait_for_selector(sel, timeout=8000)
                if clear:
                    await self.page.fill(sel, "")
                await self.page.type(sel, text, delay=35)
            except Exception:
                name = re.sub(r"input\[name=['\"]?|['\"]?\]", "", sel)
                await self.page.evaluate(f"""
                    const el = document.querySelector('[name="{name}"]') ||
                               document.querySelector('{sel.replace(chr(39), chr(92)+chr(39))}') ||
                               document.querySelector('div[contenteditable]') ||
                               document.querySelector('textarea');
                    if (el) {{
                        el.focus();
                        if (el.contentEditable === 'true') {{
                            document.execCommand('insertText', false, {json.dumps(text)});
                        }} else {{
                            el.value = {json.dumps(text)};
                            el.dispatchEvent(new Event('input', {{bubbles:true}}));
                        }}
                    }}
                """)
            await asyncio.sleep(0.4)

        elif act == "press":
            key = action.get("key", "Enter")
            await self.page.keyboard.press(key)
            await asyncio.sleep(0.5)

        elif act == "wait_for_login":
            url_contains = action.get("url_contains", "")
            desc = action.get("description", "Waiting for manual login...")
            await self.emit({"type": "step", "action": "navigate", "description": f"⏳ {desc} — log in manually in the browser window"})

            LOGIN_INDICATORS = [
                "auth", "login", "signin", "sign-in", "accounts.google",
                "auth0", "sso", "oauth", "qr", "scan"
            ]
            LOGGED_IN_INDICATORS = [
                "chat.openai.com/c/", "chatgpt.com/c/", "chatgpt.com/?",
                "web.whatsapp.com/#", "web.whatsapp.com/",
            ]

            # Poll for up to 3 minutes waiting for login to complete
            for i in range(180):
                await asyncio.sleep(1)
                current_url = self.page.url.lower()

                # Check if we look logged in
                is_on_login = any(ind in current_url for ind in LOGIN_INDICATORS)
                is_logged_in = not is_on_login

                # Also check page content for login signals
                try:
                    page_text = await self.page.evaluate("() => document.body?.innerText?.slice(0, 200) || ''")
                    page_text_lower = page_text.lower()
                    has_login_form = any(x in page_text_lower for x in ["log in", "sign in", "password", "scan qr", "keep me logged"])
                    if has_login_form:
                        is_logged_in = False
                except Exception:
                    pass

                # For ChatGPT: wait for chat interface
                if "chatgpt" in url_contains or "openai" in url_contains:
                    try:
                        chat_ready = await self.page.query_selector("div[contenteditable='true'], #prompt-textarea, main form textarea")
                        if chat_ready:
                            is_logged_in = True
                    except Exception:
                        pass

                # For WhatsApp: wait for chat list
                if "whatsapp" in url_contains:
                    try:
                        wa_ready = await self.page.query_selector("div[aria-label='Chat list'], div[data-tab='3']")
                        if wa_ready:
                            is_logged_in = True
                    except Exception:
                        pass

                if is_logged_in:
                    await self.emit({"type": "step", "action": "navigate", "description": f"✅ Login detected after {i}s — continuing task"})
                    await asyncio.sleep(2)
                    ss = await self._screenshot()
                    await self.emit({"type": "screenshot", "screenshot": ss, "description": "Logged in — resuming"})
                    break

                # Send periodic update screenshots every 10s
                if i % 10 == 0 and i > 0:
                    ss = await self._screenshot()
                    await self.emit({"type": "screenshot", "screenshot": ss, "description": f"⏳ Waiting for login... ({i}s)"})

        elif act == "wait_for":
            sel = action["selector"]
            timeout = action.get("timeout", 15000)
            await self.emit({"type": "step", "action": "navigate", "description": f"Waiting for: {sel}"})
            try:
                await self.page.wait_for_selector(sel, timeout=timeout)
                await asyncio.sleep(2)
            except Exception:
                pass
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": "Element appeared"})

        elif act == "wait":
            await asyncio.sleep(action.get("ms", 1000) / 1000)

        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 500)
            dy = amount if direction == "down" else -amount
            await self.page.evaluate(f"window.scrollBy(0, {dy})")
            await asyncio.sleep(0.5)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"Scrolled {direction}"})

        elif act == "hover":
            sel = action["selector"]
            try:
                await self.page.hover(sel, timeout=5000)
                await asyncio.sleep(0.3)
            except Exception:
                pass

        elif act == "select":
            sel = action["selector"]
            value = action["value"]
            await self.page.select_option(sel, value=value, timeout=6000)
            await asyncio.sleep(0.5)

        elif act == "save_screenshot":
            filename = action.get("filename", f"screenshot_{self.task_id[:8]}.png")
            desc = action.get("description", "saved screenshot")
            # Strip any screenshots/ prefix the LLM may add to avoid double nesting
            filename = Path(filename).name  # keep only the bare filename
            filepath = SCREENSHOTS_DIR / filename
            await self.emit({"type": "step", "action": "navigate", "description": f"Saving screenshot: {filename}"})
            buf = await self.page.screenshot(type="png", full_page=False)
            filepath.write_bytes(buf)
            ss = base64.b64encode(buf).decode()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"Saved: {filepath}"})
            return str(filepath.absolute())

        elif act == "upload_file":
            sel = action.get("selector", "input[type='file']")
            filepath = action.get("filepath", "")
            await self.emit({"type": "step", "action": "type", "description": f"Uploading: {filepath}"})
            try:
                fpath = Path(filepath)
                # Always try bare filename in SCREENSHOTS_DIR first
                bare = SCREENSHOTS_DIR / fpath.name
                if bare.exists():
                    fpath = bare
                elif not fpath.is_absolute():
                    fpath = Path(__file__).parent / filepath
                file_input = await self.page.query_selector(sel)
                if not file_input:
                    # Try to find any file input
                    file_input = await self.page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(str(fpath))
                    await asyncio.sleep(2)
                    ss = await self._screenshot()
                    await self.emit({"type": "screenshot", "screenshot": ss, "description": "File uploaded"})
                else:
                    raise Exception("No file input found on page")
            except Exception as e:
                raise Exception(f"Upload failed: {e}")

        elif act == "extract":
            sel = action["selector"]
            desc = action.get("description", "data")
            await self.emit({"type": "step", "action": "navigate", "description": f"Extracting: {desc}"})
            try:
                safe_sel = sel.replace("'", "\\'")
                data = await self.page.evaluate(f"""() => {{
                    try {{
                        const els = document.querySelectorAll('{safe_sel}');
                        return Array.from(els).map(e => (e.innerText || e.textContent || '').trim()).filter(Boolean);
                    }} catch(e) {{ return ['Selector error: ' + e.message]; }}
                }}""")
            except Exception:
                data = []
            if not data or 'error' in str(data[0]).lower():
                data = await self.page.evaluate("""() =>
                    Array.from(document.querySelectorAll('td,th,li,p,h2,h3'))
                    .map(e => (e.innerText||'').trim())
                    .filter(s => s.length > 1 && s.length < 300)
                    .slice(0, 60)
                """)
            await self.emit({"type": "extract", "description": desc, "data": data[:60]})
            return json.dumps(data[:60])

        elif act == "extract_text":
            desc = action.get("description", "page text")
            data = await self.page.evaluate("""() =>
                Array.from(document.querySelectorAll('p,h1,h2,h3,li,td,th,span,a,div[class]'))
                .map(e => (e.innerText||'').trim())
                .filter(s => s.length > 2 && s.length < 400)
                .slice(0, 80)
            """)
            await self.emit({"type": "extract", "description": desc, "data": data[:80]})
            return json.dumps(data[:80])

        elif act == "screenshot":
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": action.get("description", "screenshot")})

        elif act == "fill_google_form":
            fields = action.get("fields", {})
            desc = action.get("description", "Filling Google Form")
            await self.emit({"type": "step", "action": "type", "description": f"Filling form fields: {list(fields.keys())}"})
            result = await fill_google_form(self.page, fields)
            filled = result.get("filled", [])
            await self.emit({"type": "extract", "description": "Form fields filled", "data": filled})
            await asyncio.sleep(1)
            ss = await self._screenshot()
            await self.emit({"type": "screenshot", "screenshot": ss, "description": f"Form filled: {', '.join(filled)}"})

        elif act == "done":
            return action.get("result", "Task completed.")

        elif act == "error":
            raise Exception(action.get("message", "Agent error"))

        return None

    async def verify(self, task: str, executed: list) -> dict:
        context = await self.get_page_context()
        ss = context.get("screenshot", "")
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": f"Task: {task}\nActions done: {json.dumps([a.get('description', a.get('action')) for a in executed])}\nURL: {context['url']}\nTitle: {context['title']}"}
        ]}]
        if ss:
            msgs[0]["content"].insert(0, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ss}"}})
        resp = await self.client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "system", "content": VERIFY_PROMPT}] + msgs,
            max_tokens=300, temperature=0,
        )
        raw = re.sub(r"```json\s*|\s*```", "", resp.choices[0].message.content.strip())
        try:
            return json.loads(raw)
        except Exception:
            return {"success": True, "summary": raw, "issues": ""}

    async def run(self, task: str) -> str:
        retry_hint = ""
        for attempt in range(self.max_retries + 1):
            context = await self.get_page_context()
            await self.emit({"type": "screenshot", "screenshot": context["screenshot"], "description": "Initial state"})
            actions = await self.plan(task, context, retry_hint)
            await self.emit({"type": "plan", "actions": actions, "count": len(actions)})

            result = None
            executed = []

            for action in actions:
                try:
                    outcome = await self.execute_action(action)
                    executed.append(action)
                    if action.get("action") == "done":
                        result = outcome
                        break
                except Exception as e:
                    err_msg = str(e)
                    await self.emit({"type": "step_error", "action": action, "error": err_msg})
                    retry_hint = f"Action '{action.get('action')}' failed: {err_msg}. Use different selectors or approach."
                    break

            if result:
                verification = await self.verify(task, executed)
                return verification.get("summary", result)

            if attempt < self.max_retries:
                await self.emit({"type": "retry", "attempt": attempt + 1, "hint": retry_hint})
                await asyncio.sleep(1)

        return f"Completed {len(executed)} actions. Final URL: {self.page.url}"


async def fill_google_form(page, fields: dict) -> str:
    """
    Dedicated Google Form filler — handles Google Forms specific DOM structure.
    fields = {
      "DATE": "2025-06-28",
      "TIME": "15:45",
      "NAME": "Saladi Manikanta",
      "EMPLOYEE ID": "TEN/AI/810186",
      "DOMAIN": "AI"
    }
    """
    import asyncio

    await asyncio.sleep(2)

    # Get all question containers
    result = await page.evaluate("""(fields) => {
        const log = [];
        const filled = [];

        // Google Forms question containers
        const questions = document.querySelectorAll('div[role="listitem"], div.Qr7Oae, div.freebirdFormviewerViewItemsItemItem');

        questions.forEach((q, idx) => {
            const labelEl = q.querySelector('div[role="heading"], span.M7eMe, div.freebirdFormviewerViewItemsItemItemTitle');
            const label = (labelEl?.innerText || '').trim().toUpperCase();
            log.push(`Q${idx}: ${label}`);

            // DATE field
            if (label.includes('DATE') && fields.DATE) {
                const input = q.querySelector('input[type="date"], input.whsOnd');
                if (input) {
                    input.value = fields.DATE;
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                    filled.push('DATE: ' + fields.DATE);
                }
            }

            // TIME field
            if (label.includes('TIME') && fields.TIME) {
                const input = q.querySelector('input[type="time"], input.whsOnd');
                if (input) {
                    input.value = fields.TIME;
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                    filled.push('TIME: ' + fields.TIME);
                }
            }

            // NAME field
            if (label.includes('NAME') && fields.NAME) {
                const input = q.querySelector('input.whsOnd, input[type="text"], textarea');
                if (input) {
                    input.focus();
                    input.value = fields.NAME;
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    filled.push('NAME: ' + fields.NAME);
                }
            }

            // EMPLOYEE ID field
            if ((label.includes('EMPLOYEE') || label.includes('ID')) && fields['EMPLOYEE ID']) {
                const input = q.querySelector('input.whsOnd, input[type="text"], textarea');
                if (input) {
                    input.focus();
                    input.value = fields['EMPLOYEE ID'];
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    filled.push('EMPLOYEE ID: ' + fields['EMPLOYEE ID']);
                }
            }

            // DOMAIN - radio button
            if (label.includes('DOMAIN') && fields.DOMAIN) {
                // Try radio/checkbox options
                const options = q.querySelectorAll('div[role="radio"], div[role="checkbox"], label, span.aDTYNe');
                options.forEach(opt => {
                    const optText = (opt.innerText || opt.textContent || '').trim().toUpperCase();
                    if (optText === fields.DOMAIN.toUpperCase() || optText.includes(fields.DOMAIN.toUpperCase())) {
                        opt.click();
                        filled.push('DOMAIN: ' + fields.DOMAIN);
                    }
                });
            }
        });

        return {log, filled};
    }""", {
        "DATE": fields.get("DATE", ""),
        "TIME": fields.get("TIME", ""),
        "NAME": fields.get("NAME", ""),
        "EMPLOYEE ID": fields.get("EMPLOYEE ID", ""),
        "DOMAIN": fields.get("DOMAIN", ""),
    })

    return result
