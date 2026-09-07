import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path

from app.database.database import SessionLocal
from app.database.models import PriceAlert, Session, WishlistItem
from app.schemas.dashboard import PriceAlertRequest, WishlistRequest

router = APIRouter()


def _get_or_create_session(db, session_id: str) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        session = Session(session_id=session_id, created_at=datetime.now(timezone.utc))
        db.add(session)
        db.flush()
    return session


@router.get("/wishlist/{session_id}")
def list_wishlist(session_id: str = Path(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")):
    db = SessionLocal()
    try:
        rows = db.query(WishlistItem).filter(WishlistItem.session_id == session_id).order_by(WishlistItem.created_at.desc()).all()
        return {"status": "success", "items": [{"id": row.id, "product": json.loads(row.product_json), "created_at": row.created_at} for row in rows]}
    finally:
        db.close()


@router.post("/wishlist")
def add_wishlist(payload: WishlistRequest):
    db = SessionLocal()
    try:
        _get_or_create_session(db, payload.session_id)
        encoded = json.dumps(payload.product, ensure_ascii=False, sort_keys=True)
        existing = db.query(WishlistItem).filter(WishlistItem.session_id == payload.session_id, WishlistItem.product_json == encoded).first()
        if existing:
            return {"status": "success", "item": {"id": existing.id, "product": payload.product}, "already_exists": True}
        row = WishlistItem(session_id=payload.session_id, product_json=encoded)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"status": "success", "item": {"id": row.id, "product": payload.product}, "already_exists": False}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/wishlist/{session_id}/{item_id}")
def remove_wishlist(session_id: str, item_id: int):
    db = SessionLocal()
    try:
        row = db.query(WishlistItem).filter(WishlistItem.id == item_id, WishlistItem.session_id == session_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Wishlist item not found")
        db.delete(row)
        db.commit()
        return {"status": "success"}
    finally:
        db.close()


@router.get("/alerts/{session_id}")
def list_alerts(session_id: str = Path(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")):
    db = SessionLocal()
    try:
        rows = db.query(PriceAlert).filter(PriceAlert.session_id == session_id).order_by(PriceAlert.created_at.desc()).all()
        return {"status": "success", "alerts": [{"id": row.id, "search_query": row.search_query, "target_price": row.target_price, "active": bool(row.active), "created_at": row.created_at} for row in rows]}
    finally:
        db.close()


@router.post("/alerts")
def create_alert(payload: PriceAlertRequest):
    db = SessionLocal()
    try:
        _get_or_create_session(db, payload.session_id)
        row = PriceAlert(session_id=payload.session_id, search_query=payload.search_query.strip(), target_price=payload.target_price, active=1)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"status": "success", "alert": {"id": row.id, "search_query": row.search_query, "target_price": row.target_price, "active": True}}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/alerts/{session_id}/{alert_id}")
def delete_alert(session_id: str, alert_id: int):
    db = SessionLocal()
    try:
        row = db.query(PriceAlert).filter(PriceAlert.id == alert_id, PriceAlert.session_id == session_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Price alert not found")
        db.delete(row)
        db.commit()
        return {"status": "success"}
    finally:
        db.close()
