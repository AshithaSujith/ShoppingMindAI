import os
import json
from datetime import datetime

from crud import create_session, save_message

CHAT_SESSIONS_DIR = "chat_sessions"


def migrate():

    if not os.path.exists(CHAT_SESSIONS_DIR):
        print("chat_sessions folder not found.")
        return

    files = [
        f for f in os.listdir(CHAT_SESSIONS_DIR)
        if f.endswith(".json")
    ]

    print(f"Found {len(files)} session files.\n")

    migrated_sessions = 0
    migrated_messages = 0

    for filename in files:

        filepath = os.path.join(CHAT_SESSIONS_DIR, filename)

        try:

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            session_id = data.get("session_id")

            if not session_id:
                print(f"Skipping {filename} (No session_id)")
                continue

            create_session(session_id)

            for msg in data.get("messages", []):

                role = msg.get("role")
                content = msg.get("content")

                if not role or not content:
                    continue

                save_message(
                    session_id=session_id,
                    role=role,
                    message=content
                )

                migrated_messages += 1

            migrated_sessions += 1
            print(f"✓ Migrated {session_id}")

        except Exception as e:
            print(f"✗ Failed {filename}")
            print(e)

    print("\n--------------------------------")
    print(f"Sessions Migrated : {migrated_sessions}")
    print(f"Messages Migrated : {migrated_messages}")
    print("--------------------------------")


if __name__ == "__main__":
    migrate()