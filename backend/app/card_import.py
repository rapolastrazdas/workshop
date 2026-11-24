import re
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DeckCard

MAIN_CARD_LIMIT = 500


def normalize_card_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).casefold()
    return " ".join(name.translate(str.maketrans("", "", ",'’‘")).split())


def card_name_keys(name: str) -> list[str]:
    return sorted({normalize_card_name(name), normalize_card_name(name.split("//", 1)[0])})


@dataclass
class ImportLine:
    text: str
    name: str
    quantity: int
    list_name: str


class UnrecognizedLine(BaseModel):
    text: str
    list_name: str


class ImportResult(BaseModel):
    imported: int = 0
    unrecognized_lines: list[UnrecognizedLine] = Field(default_factory=list)
    skipped_main: int = 0


def parse_card_list(card_list: str) -> tuple[list[ImportLine], list[UnrecognizedLine]]:
    lines = []
    unrecognized = []
    list_name = "main"
    for raw in card_list.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.casefold() in {"svarstomos", "maybeboard"}:
            list_name = "maybeboard"
            continue
        if line.casefold() in {"deck", "sideboard"}:
            unrecognized.append(UnrecognizedLine(text=line, list_name=list_name))
            continue
        match = re.fullmatch(r"([0-9]+)[xX]?\s+(.+)", line)
        quantity = 1
        name = line
        if match:
            amount, name = match.groups()
            if len(amount) > 10 or not 0 < int(amount) <= 2_147_483_647:
                unrecognized.append(UnrecognizedLine(text=line, list_name=list_name))
                continue
            quantity = int(amount)
        elif re.match(r"^[+-]?[0-9]+(?:[xX]|\.[0-9]+)?\s", line):
            unrecognized.append(UnrecognizedLine(text=line, list_name=list_name))
            continue
        lines.append(ImportLine(line, normalize_card_name(name), quantity, list_name))
    return lines, unrecognized


def apply_card_import(db: Session, deck_id: int, lines: list[ImportLine],
                      oracle_ids: dict[str, str], unrecognized: list[UnrecognizedLine]) -> ImportResult:
    result = ImportResult(unrecognized_lines=list(unrecognized))
    rows = db.scalars(select(DeckCard).where(DeckCard.deck_id == deck_id)).all()
    existing = {(row.oracle_id, row.list_name): row for row in rows}
    main_count = sum(row.quantity for row in rows if row.list_name == "main")
    for line in lines:
        oracle_id = oracle_ids.get(line.name)
        if oracle_id is None:
            result.unrecognized_lines.append(UnrecognizedLine(text=line.text, list_name=line.list_name))
            continue
        quantity = line.quantity
        if line.list_name == "main":
            quantity = min(quantity, max(0, MAIN_CARD_LIMIT - main_count))
            result.skipped_main += line.quantity - quantity
            main_count += quantity
        if not quantity:
            continue
        key = (oracle_id, line.list_name)
        row = existing.get(key)
        if row is not None:
            if row.quantity + quantity > 2_147_483_647:
                raise ValueError("Per didelis vienos kortos kiekis svarstomų kortų sąraše.")
            row.quantity += quantity
        else:
            row = DeckCard(deck_id=deck_id, oracle_id=oracle_id, list_name=line.list_name, quantity=quantity)
            db.add(row)
            existing[key] = row
        result.imported += quantity
    return result
