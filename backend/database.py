import json
import os
import time
from typing import Optional

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class Database:
    """
    Uses Supabase if credentials are provided, otherwise falls back to in-memory store.
    In-memory store works perfectly for demo / single-instance deployments.
    """

    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self._supabase: Optional[Client] = None
        self._memory: dict = {}

        if SUPABASE_AVAILABLE and url and key:
            try:
                self._supabase = create_client(url, key)
                print("Using Supabase for persistence.")
            except Exception as e:
                print(f"Supabase init failed, using in-memory: {e}")
        else:
            print("Using in-memory store (no Supabase credentials).")

    # ── Task CRUD ──────────────────────────────────────────

    async def save_task(self, task: dict):
        task["steps"] = json.dumps(task.get("steps", []))
        if self._supabase:
            self._supabase.table("tasks").insert(task).execute()
        self._memory[task["id"]] = {**task, "steps": []}

    async def update_task(self, task_id: str, updates: dict):
        if self._supabase:
            try:
                self._supabase.table("tasks").update(updates).eq("id", task_id).execute()
            except Exception:
                pass
        if task_id in self._memory:
            self._memory[task_id].update(updates)

    async def append_step(self, task_id: str, step: dict):
        if task_id in self._memory:
            if "steps" not in self._memory[task_id]:
                self._memory[task_id]["steps"] = []
            self._memory[task_id]["steps"].append(step)

    async def get_task(self, task_id: str) -> Optional[dict]:
        if self._supabase:
            try:
                res = self._supabase.table("tasks").select("*").eq("id", task_id).single().execute()
                data = res.data
                if data and isinstance(data.get("steps"), str):
                    data["steps"] = json.loads(data["steps"] or "[]")
                return data
            except Exception:
                pass
        mem = self._memory.get(task_id)
        if mem:
            return dict(mem)
        return None

    async def list_tasks(self) -> list:
        if self._supabase:
            try:
                res = self._supabase.table("tasks").select("id,task,status,created_at,result").order("created_at", desc=True).limit(50).execute()
                return res.data or []
            except Exception:
                pass
        tasks = list(self._memory.values())
        tasks.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return [{"id": t["id"], "task": t["task"], "status": t["status"], "created_at": t.get("created_at"), "result": t.get("result")} for t in tasks[:50]]

    async def delete_task(self, task_id: str):
        if self._supabase:
            try:
                self._supabase.table("tasks").delete().eq("id", task_id).execute()
            except Exception:
                pass
        self._memory.pop(task_id, None)
