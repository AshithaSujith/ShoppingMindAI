import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schemas.requests import ClearRequest

from app.api.search import router as search_router
from app.api.session import router as session_router
from app.services.chatbot import ChatBot
from app.database.database import Base, engine
import app.database.models


app = FastAPI()
chatbot = ChatBot()
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(search_router)
app.include_router(session_router)

@app.get("/")
async def root():
    return {"message": "ShopMind AI API Running"}


@app.post("/session/clear")
async def clear_session(payload: ClearRequest):
    print("NEW CHAT:", payload.session_id)

    return {
        "status": "success",
        "message": "New session started"
    }


@app.get("/session/history/{session_id}")
async def get_history(session_id: str):
    history = chatbot.get_history(session_id)
    return {"status": "success", "session_id": session_id, "messages": history}


