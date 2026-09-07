from app.database.crud import get_history, save_message

session_id = "test_session_002"

save_message(session_id, "user", "Hello")

save_message(session_id, "assistant", "Hi!")

history = get_history(session_id)

print(history)
