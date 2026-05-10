from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, list_conversations, get_conversation, get_messages


router = APIRouter()


@router.get("/conversations")
async def conversations_list(db: AsyncSession = Depends(get_db)):
    convs = await list_conversations(db)
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    msgs = await get_messages(db, conversation_id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "image_path": m.image_path,
            "created_at": m.created_at,
        }
        for m in msgs
    ]
