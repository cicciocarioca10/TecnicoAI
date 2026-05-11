import base64
import os
import traceback
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
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
from services.auth_service import get_current_user
from services.question_engine import (
    detect_technical_request,
    has_clarifications_been_asked,
    build_system_prompt,
    should_search,
)
from services.search_service import search_technical_info
from services.ai_service import send_message


router = APIRouter()


class ConversationCreate(BaseModel):
    title: str = "Nuova conversazione"


@router.post("/conversations")
async def new_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conv = await create_conversation(db, body.title, user_id=current_user.id)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conv = await get_conversation(db, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    await delete_conversation(db, conversation_id)
    return {"ok": True}


@router.post("/chat")
async def chat(
    conversation_id: int = Form(...),
    message: str = Form(...),
    model: str = Form("claude"),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if model not in ("claude", "deepseek"):
        raise HTTPException(status_code=422, detail="Modello non supportato")

    conv = await get_conversation(db, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")

    image_base64: Optional[str] = None
    image_type: str = "image/jpeg"
    saved_path: Optional[str] = None

    if image and image.filename:
        os.makedirs("uploads", exist_ok=True)
        ext = os.path.splitext(image.filename)[1] or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join("uploads", filename)
        data = await image.read()
        with open(filepath, "wb") as f:
            f.write(data)
        saved_path = f"/uploads/{filename}"
        image_base64 = base64.b64encode(data).decode()
        image_type = image.content_type or "image/jpeg"

    history = await get_messages(db, conversation_id)
    messages_for_ai = [{"role": m.role, "content": m.content} for m in history]

    is_technical = detect_technical_request(message)
    clarifications_asked = has_clarifications_been_asked(messages_for_ai)

    search_context = ""
    if should_search(message):
        search_context = await search_technical_info(message)

    system_prompt = build_system_prompt(is_technical, clarifications_asked, search_context)

    await create_message(db, conversation_id, "user", message, image_path=saved_path)
    messages_for_ai.append({"role": "user", "content": message})

    try:
        reply = await send_message(
            messages_for_ai,
            system_prompt=system_prompt,
            model=model,
            image_base64=image_base64,
            image_type=image_type,
        )
    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc())

    await create_message(db, conversation_id, "assistant", reply)
    return {"reply": reply, "conversation_id": conversation_id}


@router.get("/uploads/{filename}")
async def get_upload(filename: str):
    filepath = os.path.join("uploads", filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(filepath)
