import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import count_users, get_db, get_user_by_email, create_user
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_response(user, token: str) -> dict:
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password minimo 8 caratteri")
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email già registrata")
    user = await create_user(db, body.email, hash_password(body.password), body.full_name)
    return _user_response(user, create_access_token(user.id, user.email))


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabilitato")
    return _user_response(user, create_access_token(user.id, user.email))


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
    }


@router.post("/logout")
async def logout():
    return {"ok": True}


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*" for c in pwd)
        ):
            return pwd


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup_first_admin(db: AsyncSession = Depends(get_db)):
    if await count_users(db) > 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup già completato")
    email = f"admin@tecnicoai.it"
    password = _generate_password()
    user = await create_user(db, email, hash_password(password), "Admin", is_admin=True)
    logger.info("SETUP: utente creato %s", email)
    return {
        "email": email,
        "password": password,
        "message": "Admin creato. Salva queste credenziali — non verranno mostrate di nuovo.",
    }
