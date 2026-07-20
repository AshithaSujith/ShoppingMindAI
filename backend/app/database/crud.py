from sqlalchemy import desc
from datetime import datetime

from app.database.database import SessionLocal
from app.database.models import Session as SessionModel
from app.database.models import Message


def create_session(session_id: str):

    db = SessionLocal()

    try:

        existing = (
            db.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .first()
        )

        if existing:
            return existing

        session = SessionModel(
            session_id=session_id,
            created_at=datetime.now()
        )

        db.add(session)
        db.commit()

        return session

    finally:
        db.close()


def save_message(
    session_id: str,
    role: str,
    message: str
):

    db = SessionLocal()

    try:

        create_session(session_id)

        new_message = Message(
            session_id=session_id,
            role=role,
            message=message,
            created_at=datetime.now()
        )

        db.add(new_message)
        db.commit()

    finally:
        db.close()


def get_history(session_id: str):

    db = SessionLocal()

    try:

        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.id)
            .all()
        )

        return [
            {
                "role": m.role,
                "content": m.message
            }
            for m in messages
        ]

    finally:
        db.close()


def clear_session(session_id: str):

    db = SessionLocal()

    try:

        (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .delete()
        )

        db.commit()

    finally:
        db.close()


def delete_session(session_id: str):

    db = SessionLocal()

    try:

        (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .delete()
        )

        (
            db.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .delete()
        )

        db.commit()

    finally:
        db.close()


def get_all_sessions():

    db = SessionLocal()

    try:

        sessions = (
            db.query(SessionModel)
            .order_by(desc(SessionModel.created_at))
            .all()
        )

        result = []

        for session in sessions:

            count = (
                db.query(Message)
                .filter(Message.session_id == session.session_id)
                .count()
            )

            result.append(
                {
                    "session_id": session.session_id,
                    "message_count": count,
                    "last_active": session.created_at,
                }
            )

        return result

    finally:
        db.close()

def save_conversation(
    session_id: str,
    user_message: str,
    assistant_message: str,
):
    save_message(session_id, "user", user_message)
    save_message(session_id, "assistant", assistant_message)