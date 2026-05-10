from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import (
    get_db,
    create_conversation,
    get_conversation,
    delete_conversation,
    create_message,
    get_messages,
)
from services.question_engine import detect_technical_request, has_clarifications_been_asked, build_system_prompt
from services.ai_service import send_message


router = APIRouter()


class ConversationCreate(BaseModel):
    title: str = "Nuova conversazione"


class ChatRequest(BaseModel):
    conversation_id: int
    message: str
    model: Literal["claude", "deepseek"] = "claude"


@router.post("/conversations")
async def new_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = await create_conversation(db, body.title)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    await delete_conversation(db, conversation_id)
    return {"ok": True}


@router.post("/chat")
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, body.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")

    history = await get_messages(db, body.conversation_id)
    messages_for_ai = [{"role": m.role, "content": m.content} for m in history]

    is_technical = detect_technical_request(body.message)
    clarifications_asked = has_clarifications_been_asked(messages_for_ai)
    system_prompt = build_system_prompt(is_technical, clarifications_asked)

    await create_message(db, body.conversation_id, "user", body.message)

    messages_for_ai.append({"role": "user", "content": body.message})

    try:
        reply = await send_message(messages_for_ai, system_prompt=system_prompt, model=body.model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Servizio AI non disponibile") from exc

    await create_message(db, body.conversation_id, "assistant", reply)

    return {"reply": reply, "conversation_id": body.conversation_id}
