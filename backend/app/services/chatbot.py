from app.database.crud import (
    save_message,
    save_conversation,
    get_history,
    clear_session,
    delete_session,
    get_all_sessions,
)


class ChatBot:

    def __init__(self):
        pass

    def get_history(self, session_id: str):
        return get_history(session_id)

    def add_message(self, session_id: str, role: str, content: str):
        save_message(
            session_id=session_id,
            role=role,
            message=content,
        )

    def clear(self, session_id: str):
        clear_session(session_id)

    def delete(self, session_id: str):
        delete_session(session_id)

    def get_all_sessions(self):
        return get_all_sessions()

    def save_conversation(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ):
        save_conversation(
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )