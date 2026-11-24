import hashlib
import os
import secrets
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, TypeAdapter, ValidationError
from pwdlib import PasswordHash
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, User

app = FastAPI(title="Urza's Workshop", version="0.1.0")
passwords = PasswordHash.recommended()
# Verify a real hash for unknown accounts too, avoiding an obvious timing shortcut.
dummy_hash = passwords.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
email_adapter = TypeAdapter(EmailStr)
session_minutes = int(os.getenv("SESSION_MINUTES", "60"))
if not 1 <= session_minutes <= 1440:
    raise ValueError("SESSION_MINUTES must be between 1 and 1440")

Db = Annotated[Session, Depends(get_db)]
INVALID_LOGIN = "Neteisingas el. pašto adresas arba slaptažodis."
EXPIRED_SESSION = "Jūsų sesija baigėsi. Prisijunkite iš naujo."


class Registration(BaseModel):
    email: str
    password: str
    password_confirmation: str


class Login(BaseModel):
    email: str
    password: str


class AccountDeletion(BaseModel):
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class SessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserOut


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(db: Session, user: User) -> SessionOut:
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + session_minutes * 60
    # Remove expired credentials instead of accumulating them indefinitely.
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= int(time.time())))
    db.add(AuthSession(token_hash=fingerprint(token), user_id=user.id, expires_at=expires_at))
    return SessionOut(access_token=token, expires_at=expires_at, user=UserOut.model_validate(user))


def require_session(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthSession:
    session = db.get(AuthSession, fingerprint(credentials.credentials)) if credentials else None
    if session is None or session.expires_at <= int(time.time()):
        raise HTTPException(401, EXPIRED_SESSION, headers={"WWW-Authenticate": "Bearer"})
    return session


CurrentSession = Annotated[AuthSession, Depends(require_session)]


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/health")
def health(db: Db):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=SessionOut, status_code=201)
def register(data: Registration, db: Db):
    errors = {}
    try:
        email = str(email_adapter.validate_python(data.email.strip())).lower()
    except ValidationError:
        email = ""
        errors["email"] = "Įveskite teisingą el. pašto adresą."
    if len(data.password) <= 8:
        errors["password"] = "Slaptažodį turi sudaryti daugiau nei 8 simboliai."
    elif len(data.password) > 1024:
        errors["password"] = "Slaptažodis negali būti ilgesnis nei 1024 simboliai."
    if data.password != data.password_confirmation:
        errors["password_confirmation"] = "Slaptažodžiai nesutampa."
    if errors:
        raise HTTPException(422, {"errors": errors})
    user = User(email=email, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
        result = new_session(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, {"errors": {"email": "Šis el. paštas jau užregistruotas."}}) from None
    return result


@app.post("/api/auth/login", response_model=SessionOut)
def login(data: Login, db: Db):
    email = data.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Bound hashing work for unreasonable input without revealing account existence.
    password = data.password if len(data.password) <= 1024 else ""
    valid = passwords.verify(password, user.password_hash if user else dummy_hash)
    if user is None or not valid or len(data.password) > 1024:
        raise HTTPException(401, INVALID_LOGIN)
    result = new_session(db, user)
    db.commit()
    return result


@app.get("/api/auth/me", response_model=UserOut)
def me(session: CurrentSession, db: Db):
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, EXPIRED_SESSION)
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(session: CurrentSession, db: Db):
    db.delete(session)
    db.commit()
    return Response(status_code=204)


@app.delete("/api/auth/account", status_code=204)
def delete_account(data: AccountDeletion, session: CurrentSession, db: Db):
    # Lock the account while confirming and deleting its dependent records.
    user = db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    if user is None:
        raise HTTPException(401, EXPIRED_SESSION)
    password = data.password if len(data.password) <= 1024 else ""
    if not passwords.verify(password, user.password_hash) or len(data.password) > 1024:
        raise HTTPException(403, {"errors": {"password": "Neteisingas slaptažodis."}})
    # Foreign keys cascade to decks and every session in the same transaction.
    db.delete(user)
    db.commit()
    return Response(status_code=204)


@app.get("/api/decks")
def decks(session: CurrentSession):
    # NI-01 only establishes the protected destination. Deck CRUD is a later story.
    return []


@app.get("/api/decks/{deck_id}")
def deck(deck_id: str, session: CurrentSession):
    raise HTTPException(404, "Kaladė nerasta.")
