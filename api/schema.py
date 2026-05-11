import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, get_schema, get_conversation
from services import schema_service
from services.auth_service import get_current_user

router = APIRouter()

VALID_DOMAINS = {
    "elettrico", "plc", "pneumatico", "idraulico",
    "meccatronico", "fieldbus", "safety", "auto",
}

VALID_MODELS = {"claude", "deepseek"}


class SchemaRequest(BaseModel):
    conversation_id: int
    domain: str = "auto"
    model: str = "claude"


@router.post("/schema/generate")
async def generate_schema(
    body: SchemaRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if body.domain not in VALID_DOMAINS:
        raise HTTPException(status_code=422, detail="Dominio non supportato")
    if body.model not in VALID_MODELS:
        raise HTTPException(status_code=422, detail="Modello non supportato")
    conv = await get_conversation(db, body.conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    try:
        result = await schema_service.generate_schema(
            body.conversation_id, db, domain=body.domain, model=body.model
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Errore generazione schema") from exc
    return result


@router.get("/schema/pdf/{schema_id}")
async def get_schema_pdf(
    schema_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schema = await get_schema(db, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema non trovato")
    conv = await get_conversation(db, schema.conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Schema non trovato")
    if not schema.pdf_path or not os.path.isfile(schema.pdf_path):
        raise HTTPException(status_code=404, detail="File PDF non disponibile")
    return FileResponse(
        schema.pdf_path,
        media_type="application/pdf",
        filename=f"schema-{schema_id}.pdf",
    )
