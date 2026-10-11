# BrowseAI — AI Browser Automation Agent

Plain English → real browser actions. Powered by Groq LLaMA 3 Vision + Playwright.

---

## Architecture

```
User prompt
    ↓
FastAPI backend  ←→  WebSocket (real-time events)  ←→  React frontend
    ↓
Groq LLaMA 3 Vision  (plan + verify)
    ↓
Playwright (headless Chromium)
    ↓
Screenshots + DOM extraction → back to LLM
```

---

## Free-tier stack

| Service | What for | Cost |
|---------|----------|------|
| Groq | LLaMA 3 Vision inference | Free tier (100 req/min) |
| Render.com | Backend hosting | Free (750 hrs/month) |
| Vercel | Frontend hosting | Free |
| Supabase | Task history DB | Free (500 MB) |
| Playwright | Headless browser | Open source |

---

## Local development

### 1. Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install-deps chromium  # Linux only

# Set env vars
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Run
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend

npm install

# Set backend URL
cp .env.example .env
# Edit: VITE_API_URL=http://localhost:8000

npm run dev
# → http://localhost:5173
```

---

## Get API keys (all free)

### Groq API key
1. Go to https://console.groq.com
2. Sign up (free)
3. Create API key → copy to `GROQ_API_KEY`

### Supabase (optional — in-memory fallback works without it)
1. Go to https://supabase.com → New project
2. SQL Editor → paste contents of `supabase_schema.sql` → Run
3. Settings → API → copy `URL` and `anon key`
4. Set `SUPABASE_URL` and `SUPABASE_KEY`

---

## Deploy to production (free)

### Backend → Render.com

1. Push code to GitHub
2. Go to https://render.com → New Web Service
3. Connect your repo, set root to `backend/`
4. Build command:
   ```
   pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium
   ```
5. Start command:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
   ```
6. Add env vars: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
7. Add env var: `PLAYWRIGHT_BROWSERS_PATH` = `/opt/render/project/.playwright`
8. Deploy → copy your backend URL (e.g. `https://browseai.onrender.com`)

### Frontend → Vercel

1. Go to https://vercel.com → New Project
2. Connect your repo, set root to `frontend/`
3. Add env var: `VITE_API_URL` = your Render backend URL
4. Deploy

---

## Environment variables

### Backend (.env)
```
GROQ_API_KEY=gsk_...
SUPABASE_URL=https://xxx.supabase.co        # optional
SUPABASE_KEY=eyJ...                          # optional
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8000
```

---

## Example tasks

```
Go to wikipedia.org/wiki/Python_(programming_language) and extract the key features listed in the article

Navigate to https://quotes.toscrape.com and scrape the first 5 quotes and their authors

Go to https://httpbin.org/forms/post and fill the form with customer name "Test User" and submit it

Navigate to news.ycombinator.com, screenshot the front page, and list the top 5 story titles
```

---

## Project structure

```
browser-agent/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket, task runner
│   ├── agent.py             # ReAct agent loop (plan → execute → verify)
│   ├── database.py          # Supabase + in-memory fallback
│   ├── requirements.txt
│   ├── render.yaml          # Render deployment config
│   ├── supabase_schema.sql  # DB schema
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx           # Main layout
    │   ├── App.css           # All styles
    │   ├── components/
    │   │   ├── TaskInput.tsx     # Prompt input + examples
    │   │   ├── LiveFeed.tsx      # Screenshot + timeline
    │   │   └── TaskHistory.tsx   # Sidebar history
    │   ├── hooks/
    │   │   └── useAgent.ts       # WebSocket + state
    │   └── lib/
    │       └── api.ts            # API calls + types
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── vercel.json
```

---

## Known limitations

- **Render free tier** spins down after 15 min inactivity → cold start ~30s. Fix: add a cron ping, or upgrade to paid ($7/mo).
- **Bot detection**: some sites (Cloudflare, reCAPTCHA) will block headless Chrome. Works best on public/simple sites.
- **Memory**: each task gets its own browser context, cleared after completion. State doesn't persist between tasks.
- **Concurrent tasks**: single Playwright instance handles one task at a time on free tier (1 CPU).
