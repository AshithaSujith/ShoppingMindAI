from fastapi import APIRouter

from app.schemas.requests import ClearRequest
from app.services.chatbot import ChatBot

router = APIRouter()

chatbot = ChatBot()

@router.post("/session/clear")
async def clear_session(payload: ClearRequest):
    print("NEW CHAT:", payload.session_id)
    chatbot.clear(payload.session_id)

    return {
        "status": "success",
        "message": "New session started and history cleared"
    }

@router.get("/session/history/{session_id}")
async def get_history(session_id: str):
    history = chatbot.get_history(session_id)
    return {"status": "success", "session_id": session_id, "messages": history}

