from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))


class DeckCard(Base):
    __tablename__ = "deck_cards"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_deck_cards_quantity"),
        CheckConstraint("list_name IN ('main', 'maybeboard')", name="ck_deck_cards_list_name"),
    )

    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True)
    oracle_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    list_name: Mapped[str] = mapped_column(String(16), primary_key=True, default="main")
    quantity: Mapped[int] = mapped_column(Integer)
