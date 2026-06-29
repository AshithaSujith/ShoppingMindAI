import json
import os
import time
from threading import Lock

# ─────────────────────────────────────────────────────────────────────────────
# ChatBot — persistent, thread-safe conversation memory
#
# Storage: each session is saved as a JSON file under ./chat_sessions/
# This means conversations survive server restarts.
#
# Features:
#   - Persistent storage (JSON files per session)
#   - Thread-safe (Lock per session)
#   - Auto-trims to last N messages to keep context window small
#   - Tracks last_active timestamp for each session
#   - clear() wipes history but keeps session file
#   - delete() removes the session file entirely
# ─────────────────────────────────────────────────────────────────────────────

SESSIONS_DIR  = "chat_sessions"
MAX_MESSAGES  = 20   # keep last 20 messages per session (10 turns)
MAX_SESSIONS  = 500  # prune oldest sessions when limit hit


class ChatBot:

    def __init__(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._locks: dict[str, Lock] = {}
        self._global_lock = Lock()

    # ── Internal helpers ────────────────────────────────────────────────────

    def _session_path(self, session_id: str) -> str:
        # Sanitize session_id so it's safe as a filename
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return os.path.join(SESSIONS_DIR, f"{safe}.json")

    def _get_lock(self, session_id: str) -> Lock:
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = Lock()
            return self._locks[session_id]

    def _load(self, session_id: str) -> dict:
        path = self._session_path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"session_id": session_id, "messages": [], "last_active": time.time()}

    def _save(self, session_id: str, data: dict):
        data["last_active"] = time.time()
        path = self._session_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[ChatBot] Save error for {session_id}: {e}")

    def _prune_old_sessions(self):
        """Remove oldest session files when MAX_SESSIONS is exceeded."""
        try:
            files = [
                os.path.join(SESSIONS_DIR, f)
                for f in os.listdir(SESSIONS_DIR)
                if f.endswith(".json")
            ]
            if len(files) <= MAX_SESSIONS:
                return
            # Sort by modification time, remove oldest
            files.sort(key=os.path.getmtime)
            for f in files[:len(files) - MAX_SESSIONS]:
                os.remove(f)
                print(f"[ChatBot] Pruned old session: {f}")
        except Exception as e:
            print(f"[ChatBot] Prune error: {e}")

    # ── Public API ──────────────────────────────────────────────────────────

    def get_history(self, session_id: str) -> list[dict]:
        """Return the message history for a session."""
        lock = self._get_lock(session_id)
        with lock:
            data = self._load(session_id)
            return data.get("messages", [])

    def add_message(self, session_id: str, role: str, content: str):
        """Append a message and persist. Trims to MAX_MESSAGES."""
        lock = self._get_lock(session_id)
        with lock:
            data = self._load(session_id)
            data["messages"].append({
                "role": role,
                "content": content,
                "timestamp": time.time(),
            })
            # Keep only the last MAX_MESSAGES to avoid huge context windows
            if len(data["messages"]) > MAX_MESSAGES:
                data["messages"] = data["messages"][-MAX_MESSAGES:]
            self._save(session_id, data)

        # Prune old sessions periodically (every 50 new messages roughly)
        if hash(session_id + str(time.time())) % 50 == 0:
            self._prune_old_sessions()

    def clear(self, session_id: str):
        """Wipe the conversation history for a session (keeps the file)."""
        lock = self._get_lock(session_id)
        with lock:
            data = self._load(session_id)
            data["messages"] = []
            self._save(session_id, data)

    def delete(self, session_id: str):
        """Delete the session file entirely."""
        lock = self._get_lock(session_id)
        with lock:
            path = self._session_path(session_id)
            if os.path.exists(path):
                os.remove(path)
                print(f"[ChatBot] Deleted session: {session_id}")

    def get_all_sessions(self) -> list[dict]:
        """Return summary of all active sessions (for debugging/admin)."""
        sessions = []
        try:
            for fname in os.listdir(SESSIONS_DIR):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(SESSIONS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", fname),
                        "message_count": len(data.get("messages", [])),
                        "last_active": data.get("last_active", 0),
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"[ChatBot] List error: {e}")
        return sorted(sessions, key=lambda x: x["last_active"], reverse=True)