import hashlib
import math
import os
import secrets
import time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, TypeAdapter, ValidationError
from pwdlib import PasswordHash
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, Deck, DeckCard, User
from .card_catalog import CardCatalog, CardCatalogUnavailable, MANA_COLORS, get_card_catalog
from .card_import import MAIN_CARD_LIMIT, ImportResult, apply_card_import, parse_card_list

app = FastAPI(title="Urza's Workshop", version="0.1.0")
from .search import router as search_router

app.include_router(search_router)
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


class DeckOut(BaseModel):
    id: int
    name: str
    card_count: int
    colors: list[str]
    colors_known: bool


class DeckListOut(BaseModel):
    count: int
    decks: list[DeckOut]


class DeckCardOut(BaseModel):
    oracle_id: str
    list_name: Literal["main", "maybeboard"]
    quantity: int
    name: str | None
    mana_cost: str | None
    mana_value: float | None
    is_land: bool


class DeckDetailOut(DeckOut):
    cards: list[DeckCardOut]


class DeckCreate(BaseModel):
    name: str = ""
    card_list: str = ""


class DeckSettings(BaseModel):
    name: str
    card_list: str = ""


class DeckDeletion(BaseModel):
    name: str


class CardListImport(BaseModel):
    card_list: str


class DeckWriteOut(BaseModel):
    deck: DeckOut
    import_result: ImportResult | None = None


Catalog = Annotated[CardCatalog, Depends(get_card_catalog)]


def summarize_decks(db: Session, decks: list[Deck], catalog: CardCatalog) -> list[DeckOut]:
    if not decks:
        return []
    main_cards = db.scalars(select(DeckCard).where(
        DeckCard.deck_id.in_([deck.id for deck in decks]), DeckCard.list_name == "main",
    )).all()
    oracle_ids = {card.oracle_id for card in main_cards}
    try:
        colors_by_card = catalog.colors_for(oracle_ids) if oracle_ids else {}
    except CardCatalogUnavailable:
        raise HTTPException(503, "Nepavyko gauti kortų duomenų. Bandykite dar kartą.") from None
    return deck_summaries(decks, main_cards, colors_by_card)


def deck_summaries(decks: list[Deck], main_cards: list[DeckCard], colors_by_card: dict[str, list[str]]) -> list[DeckOut]:
    counts = {deck.id: 0 for deck in decks}
    colors_by_deck: dict[int, set[str]] = {deck.id: set() for deck in decks}
    known = {deck.id: True for deck in decks}
    for card in main_cards:
        counts[card.deck_id] += card.quantity
        if card.oracle_id not in colors_by_card:
            known[card.deck_id] = False
        else:
            colors_by_deck[card.deck_id].update(colors_by_card[card.oracle_id])
    return [DeckOut(
        id=deck.id, name=deck.name, card_count=counts[deck.id],
        colors=[color for color in MANA_COLORS if color in colors_by_deck[deck.id]],
        colors_known=known[deck.id],
    ) for deck in decks]


def import_cards(db: Session, deck_id: int, card_list: str, catalog: CardCatalog) -> ImportResult:
    if len(card_list) > 200_000:
        raise HTTPException(422, {"errors": {"card_list": "Kortų sąrašas per ilgas."}})
    lines, unrecognized = parse_card_list(card_list)
    try:
        oracle_ids = catalog.find_by_names({line.name for line in lines}) if lines else {}
        return apply_card_import(db, deck_id, lines, oracle_ids, unrecognized)
    except CardCatalogUnavailable:
        raise HTTPException(503, "Nepavyko gauti kortų duomenų. Bandykite dar kartą.") from None
    except ValueError as error:
        raise HTTPException(422, {"errors": {"card_list": str(error)}}) from None


def parse_deck_id(value: str) -> int:
    if not value.isascii() or not value.isdigit() or len(value) > 10 or not 0 < int(value) <= 2_147_483_647:
        raise HTTPException(404, "Kaladė nerasta.")
    return int(value)


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


@app.get("/api/decks", response_model=DeckListOut)
def decks(session: CurrentSession, db: Db, catalog: Catalog):
    owned = list(db.scalars(select(Deck).where(Deck.user_id == session.user_id).order_by(Deck.id.desc())))
    result = summarize_decks(db, owned, catalog)
    return DeckListOut(count=len(result), decks=result)


@app.post("/api/decks", response_model=DeckWriteOut, status_code=201)
def create_deck(data: DeckCreate, session: CurrentSession, db: Db, catalog: Catalog):
    name = data.name.strip()
    if len(name) > 100:
        raise HTTPException(422, {"errors": {"name": "Pavadinimas negali būti ilgesnis nei 100 simbolių."}})
    # Serialize creations for one owner, including automatic name assignment.
    owner = db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    if owner is None:
        raise HTTPException(401, EXPIRED_SESSION)
    if not name:
        existing_names = list(db.scalars(select(Deck.name).where(Deck.user_id == owner.id)))
        number = len(existing_names) + 1
        while f"Nauja kaladė {number}" in existing_names:
            number += 1
        name = f"Nauja kaladė {number}"
    deck = Deck(user_id=owner.id, name=name)
    db.add(deck)
    db.flush()
    result = import_cards(db, deck.id, data.card_list, catalog) if data.card_list.strip() else None
    db.flush()
    response = DeckWriteOut(deck=summarize_decks(db, [deck], catalog)[0], import_result=result)
    db.commit()
    return response


@app.post("/api/decks/{deck_id}/import", response_model=DeckWriteOut)
def import_into_deck(deck_id: str, data: CardListImport, session: CurrentSession, db: Db, catalog: Catalog):
    owned = db.scalar(select(Deck).where(Deck.id == parse_deck_id(deck_id), Deck.user_id == session.user_id).with_for_update())
    if owned is None:
        raise HTTPException(404, "Kaladė nerasta.")
    result = import_cards(db, owned.id, data.card_list, catalog)
    db.flush()
    response = DeckWriteOut(deck=summarize_decks(db, [owned], catalog)[0], import_result=result)
    db.commit()
    return response


@app.put("/api/decks/{deck_id}", response_model=DeckWriteOut)
def update_deck(deck_id: str, data: DeckSettings, session: CurrentSession, db: Db, catalog: Catalog):
    owned = db.scalar(select(Deck).where(Deck.id == parse_deck_id(deck_id), Deck.user_id == session.user_id).with_for_update())
    if owned is None:
        raise HTTPException(404, "Kaladė nerasta.")
    name = data.name.strip()
    if not 1 <= len(name) <= 100:
        raise HTTPException(422, {"errors": {"name": "Pavadinimą turi sudaryti nuo 1 iki 100 simbolių."}})
    owned.name = name
    result = import_cards(db, owned.id, data.card_list, catalog) if data.card_list.strip() else None
    db.flush()
    response = DeckWriteOut(deck=summarize_decks(db, [owned], catalog)[0], import_result=result)
    db.commit()
    return response


@app.delete("/api/decks/{deck_id}", status_code=204)
def delete_deck(deck_id: str, data: DeckDeletion, session: CurrentSession, db: Db):
    owned = db.scalar(select(Deck).where(Deck.id == parse_deck_id(deck_id), Deck.user_id == session.user_id).with_for_update())
    if owned is None:
        raise HTTPException(404, "Kaladė nerasta.")
    if data.name != owned.name:
        raise HTTPException(422, {"errors": {"name": "Įvestas pavadinimas nesutampa su kaladės pavadinimu."}})
    # The existing foreign key removes main and maybeboard entries atomically.
    db.delete(owned)
    db.commit()
    return Response(status_code=204)


@app.get("/api/decks/{deck_id}", response_model=DeckDetailOut)
def deck(deck_id: str, session: CurrentSession, db: Db, catalog: Catalog):
    owned = db.scalar(select(Deck).where(Deck.id == parse_deck_id(deck_id), Deck.user_id == session.user_id))
    if owned is None:
        raise HTTPException(404, "Kaladė nerasta.")
    return deck_detail(owned, db, catalog)


def deck_detail(owned: Deck, db: Session, catalog: CardCatalog):
    cards = list(db.scalars(select(DeckCard).where(DeckCard.deck_id == owned.id)
                            .order_by(DeckCard.list_name, DeckCard.oracle_id)))
    try:
        payloads = catalog.payloads_for(
            {card.oracle_id for card in cards},
            ["name", "mana_cost", "cmc", "mana_value", "type_line", "colors"],
        ) if cards else {}
    except CardCatalogUnavailable:
        raise HTTPException(503, "Nepavyko gauti kortų duomenų. Bandykite dar kartą.") from None

    summary = deck_summaries(
        [owned], [card for card in cards if card.list_name == "main"], CardCatalog.colors_from(payloads),
    )[0]
    details = []
    for card in cards:
        payload = payloads.get(card.oracle_id, {})
        name = payload.get("name")
        mana_cost = payload.get("mana_cost")
        mana_value = payload.get("mana_value", payload.get("cmc"))
        type_line = payload.get("type_line")
        # Use the front face's card types, without subtypes such as Land in a name.
        front_types = type_line.split("//", 1)[0].split("—", 1)[0].split() if isinstance(type_line, str) else []
        details.append(DeckCardOut(
            oracle_id=card.oracle_id, list_name=card.list_name, quantity=card.quantity,
            name=name if isinstance(name, str) and name.strip() else None,
            mana_cost=mana_cost if isinstance(mana_cost, str) else None,
            mana_value=mana_value if type(mana_value) in (int, float) and math.isfinite(mana_value) and mana_value >= 0 else None,
            is_land="Land" in front_types,
        ))
    return DeckDetailOut(**summary.model_dump(), cards=details)


class CardEdit(BaseModel):
    oracle_id: UUID
    list_name: Literal["main", "maybeboard"]
    action: Literal["add", "decrease", "remove"]


@app.post("/api/decks/{deck_id}/cards", response_model=DeckDetailOut)
def edit_card(deck_id: str, data: CardEdit, session: CurrentSession, db: Db, catalog: Catalog):
    owned = db.scalar(select(Deck).where(Deck.id == parse_deck_id(deck_id),
                                         Deck.user_id == session.user_id).with_for_update())
    if owned is None:
        raise HTTPException(404, "Kaladė nerasta.")
    oracle_id = str(data.oracle_id)
    card = db.get(DeckCard, (owned.id, oracle_id, data.list_name))
    if data.action == "add":
        if card is None:
            try:
                known = catalog.payloads_for({oracle_id}, ["name"])
            except CardCatalogUnavailable:
                raise HTTPException(503, "Kortų katalogas nepasiekiamas.") from None
            if oracle_id not in known:
                raise HTTPException(422, "Kortos nėra vietiniame kataloge.")
            db.add(DeckCard(deck_id=owned.id, oracle_id=oracle_id, list_name=data.list_name, quantity=1))
        else:
            card.quantity += 1
    elif card is None:
        raise HTTPException(409, "Kortos sąraše nėra.")
    elif data.action == "remove" or card.quantity == 1:
        db.delete(card)
    else:
        card.quantity -= 1
    db.flush()
    result = deck_detail(owned, db, catalog)
    if result.card_count > MAIN_CARD_LIMIT:
        raise HTTPException(422, "Kaladėje gali būti ne daugiau kaip 500 pagrindinių kortų.")
    db.commit()
    return result
