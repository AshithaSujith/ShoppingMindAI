from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    created_at = Column(DateTime)

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        String,
        ForeignKey("sessions.session_id")
    )
    role = Column(String)
    message = Column(Text)
    created_at = Column(DateTime)

    session = relationship(
        "Session",
        back_populates="messages"
    )