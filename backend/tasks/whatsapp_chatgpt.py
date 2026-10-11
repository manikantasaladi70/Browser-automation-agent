"""
Standalone task: ChatGPT diet plan → screenshot → send via WhatsApp Web
─────────────────────────────────────────────────────────────────────────
Setup in your backend/.env:
  CHATGPT_EMAIL=your@email.com
  CHATGPT_PASSWORD=yourpassword
  WHATSAPP_CONTACT=ContactName    ← exact name as shown in WhatsApp

Run:
  cd backend
  venv\Scripts\activate
  python tasks/whatsapp_chatgpt.py
─────────────────────────────────────────────────────────────────────────
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CHATGPT_EMAIL    = os.getenv("CHATGPT_EMAIL", "")
CHATGPT_PASSWORD = os.getenv("CHATGPT_PASSWORD", "")
WHATSAPP_CONTACT = os.getenv("WHATSAPP_CONTACT", "")
OUTPUT_DIR       = Path(__file__).parent.parent / "screenshots"
SESSION_FILE     = Path(__file__).parent.parent / "chatgpt_session.json"
OUTPUT_DIR.mkdir(exist_ok=True)


def log(msg: str):
    print(f"[BrowseAI] {msg}")


async def wait_for_response_complete(page, timeout=90):
    """Poll until ChatGPT stops generating."""
    for i in range(timeout):
        await asyncio.sleep(1)
        still_generating = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button[aria-label]');
            return Array.from(btns).some(b =>
                b.getAttribute('aria-label')?.toLowerCase().includes('stop')
            );
        }""")
        if not still_generating and i > 4:
            log(f"Response complete (~{i}s)")
            return True
    return False


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,          # Must be visible for QR scan + CAPTCHAs
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # Load saved session if available
        if SESSION_FILE.exists():
            try:
                cookies = json.loads(SESSION_FILE.read_text())
                await context.add_cookies(cookies)
                log("Loaded saved ChatGPT session.")
            except Exception:
                pass

        page = await context.new_page()

        # ── STEP 1: Open ChatGPT ───────────────────────────────────────────
        log("Opening ChatGPT...")
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Handle login if needed
        current_url = page.url
        if "auth" in current_url or "login" in current_url or "accounts" in current_url:
            log("Login required...")
            if CHATGPT_EMAIL and CHATGPT_PASSWORD:
                log("Attempting auto-login...")
                try:
                    # Click Log in button if present
                    try:
                        await page.click("button:has-text('Log in')", timeout=4000)
                        await asyncio.sleep(1)
                    except Exception:
                        pass
                    await page.fill("input[name='username'], input[type='email']", CHATGPT_EMAIL)
                    await page.click("button[type='submit'], button:has-text('Continue')")
                    await asyncio.sleep(1.5)
                    await page.fill("input[name='password'], input[type='password']", CHATGPT_PASSWORD)
                    await page.click("button[type='submit'], button:has-text('Continue')")
                    await asyncio.sleep(5)
                    log("Login submitted.")
                except Exception as e:
                    log(f"Auto-login failed ({e}). Please log in manually.")
                    log("Waiting 45 seconds for manual login...")
                    await asyncio.sleep(45)
            else:
                log("No credentials found in .env.")
                log("Please log in manually in the browser window.")
                log("Waiting 45 seconds...")
                await asyncio.sleep(45)

        # Wait for chat UI
        await asyncio.sleep(3)
        log("ChatGPT loaded.")

        # ── STEP 2: Type the prompt ────────────────────────────────────────
        prompt = "Create a detailed 7-day diet plan for a healthy lifestyle. Show it as a clear table with Day, Breakfast, Lunch, Dinner, and Snacks columns."
        log(f"Typing prompt: {prompt[:50]}...")

        typed = False
        for selector in [
            "div[contenteditable='true'][data-placeholder]",
            "div[contenteditable='true']",
            "#prompt-textarea",
            "textarea[placeholder]",
        ]:
            try:
                await page.click(selector, timeout=5000)
                await page.keyboard.type(prompt, delay=25)
                typed = True
                log(f"Typed using selector: {selector}")
                break
            except Exception:
                continue

        if not typed:
            log("Could not find input box. Trying JS...")
            await page.evaluate(f"""
                const el = document.querySelector('div[contenteditable]') || document.querySelector('textarea');
                if (el) {{
                    el.focus();
                    document.execCommand('insertText', false, {json.dumps(prompt)});
                }}
            """)

        await asyncio.sleep(0.8)
        await page.keyboard.press("Enter")
        log("Prompt sent. Waiting for response...")

        # ── STEP 3: Wait for response ──────────────────────────────────────
        await wait_for_response_complete(page, timeout=90)
        await asyncio.sleep(2)

        # ── STEP 4: Screenshot the response ───────────────────────────────
        screenshot_path = OUTPUT_DIR / f"diet_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        log("Taking screenshot...")

        try:
            # Try to capture just the last assistant message
            last_msg = page.locator("[data-message-author-role='assistant']").last
            count = await page.locator("[data-message-author-role='assistant']").count()
            if count > 0:
                await last_msg.screenshot(path=str(screenshot_path))
                log("Captured assistant message screenshot.")
            else:
                await page.screenshot(path=str(screenshot_path), full_page=False)
                log("Captured full page screenshot.")
        except Exception as e:
            log(f"Targeted screenshot failed ({e}), using full page.")
            await page.screenshot(path=str(screenshot_path), full_page=False)

        log(f"✅ Screenshot saved: {screenshot_path}")

        # Save session cookies
        try:
            cookies = await context.cookies()
            SESSION_FILE.write_text(json.dumps(cookies))
            log("Session saved for next run.")
        except Exception:
            pass

        # ── STEP 5: WhatsApp Web ───────────────────────────────────────────
        if not WHATSAPP_CONTACT:
            log("\n⚠ WHATSAPP_CONTACT not set in .env. Skipping WhatsApp send.")
            log(f"Image ready at: {screenshot_path.absolute()}")
        else:
            log("\nOpening WhatsApp Web...")
            wa_page = await context.new_page()
            await wa_page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)

            log("Waiting for WhatsApp to load (scan QR if needed)...")
            # Wait for chat list to appear (means logged in)
            try:
                await wa_page.wait_for_selector("div[aria-label='Chat list']", timeout=60000)
                log("WhatsApp loaded!")
            except Exception:
                log("WhatsApp didn't load chat list. Waiting 30 more seconds...")
                await asyncio.sleep(30)

            await asyncio.sleep(2)

            # ── STEP 6: Find contact ───────────────────────────────────────
            log(f"Searching for contact: {WHATSAPP_CONTACT}")
            sent = False
            try:
                # Click search box
                await wa_page.click(
                    "div[contenteditable][data-tab='3'], button[aria-label='Search or start new chat'], div[aria-label='Search input textbox']",
                    timeout=8000
                )
                await asyncio.sleep(0.5)
                await wa_page.keyboard.type(WHATSAPP_CONTACT, delay=50)
                await asyncio.sleep(2)

                # Click the contact result
                try:
                    await wa_page.click(f"span[title='{WHATSAPP_CONTACT}']", timeout=6000)
                except Exception:
                    # Try partial match
                    await wa_page.evaluate(f"""
                        const spans = document.querySelectorAll('span[title]');
                        const match = Array.from(spans).find(s => s.title.toLowerCase().includes('{WHATSAPP_CONTACT.lower()}'));
                        if (match) match.closest('[role=listitem]')?.click();
                    """)
                await asyncio.sleep(1.5)

                # ── STEP 7: Attach and send image ─────────────────────────
                log("Attaching image...")

                # Click the attach (paperclip) button
                await wa_page.click(
                    "div[title='Attach'], button[aria-label='Attach'], span[data-icon='attach-menu-plus']",
                    timeout=8000
                )
                await asyncio.sleep(0.8)

                # Set file on the image input
                file_input = await wa_page.query_selector("input[type='file'][accept*='image'], input[type='file']")
                if file_input:
                    await file_input.set_input_files(str(screenshot_path.absolute()))
                    log("File selected.")
                    await asyncio.sleep(2)

                    # Click send
                    await wa_page.click(
                        "div[aria-label='Send'], button[aria-label='Send'], span[data-icon='send']",
                        timeout=8000
                    )
                    log(f"✅ Image sent to '{WHATSAPP_CONTACT}' on WhatsApp!")
                    sent = True
                else:
                    log("File input not found.")

            except Exception as e:
                log(f"WhatsApp send error: {e}")

            if not sent:
                log(f"\n⚠ Could not send automatically.")
                log(f"Image saved at: {screenshot_path.absolute()}")
                log("You can manually send it from WhatsApp Web.")

        # Keep browser open briefly so you can see the result
        log("\n✅ All done! Closing in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
