import logging

from fastapi import APIRouter, Path

from app.schemas.requests import ClearRequest
from app.services.chatbot import ChatBot

router = APIRouter()
chatbot = ChatBot()
logger = logging.getLogger("shoppingmind.session")


@router.post("/session/clear")
async def clear_session(payload: ClearRequest):
    chatbot.clear(payload.session_id)
    logger.info("Session cleared: %s", payload.session_id)
    return {"status": "success", "message": "New session started and history cleared"}


@router.get("/session/history/{session_id}")
async def get_history(
    session_id: str = Path(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
):
    history = chatbot.get_history(session_id)
    return {"status": "success", "session_id": session_id, "messages": history}
