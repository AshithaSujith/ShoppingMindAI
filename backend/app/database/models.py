from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(128), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    wishlist_items = relationship("WishlistItem", back_populates="session", cascade="all, delete-orphan")
    price_alerts = relationship("PriceAlert", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(128), ForeignKey("sessions.session_id"), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("Session", back_populates="messages")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(128), ForeignKey("sessions.session_id"), nullable=False, index=True)
    product_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("Session", back_populates="wishlist_items")


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(128), ForeignKey("sessions.session_id"), nullable=False, index=True)
    search_query = Column(String(500), nullable=False)
    target_price = Column(Float, nullable=True)
    active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("Session", back_populates="price_alerts")
