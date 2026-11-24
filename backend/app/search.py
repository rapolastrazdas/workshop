import time
from collections import OrderedDict
from threading import Lock
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from .card_catalog import CardCatalog, CardCatalogUnavailable, get_card_catalog

router = APIRouter()
cache = OrderedDict()
lock = Lock()
last_request = 0.0


def card_face(card):
    return {
        "name": card.get("name") or "",
        "type": card.get("type_line") or "",
        "mana_cost": card.get("mana_cost") or "",
        "text": card.get("oracle_text") or "",
        "image": card.get("image_url") or (card.get("image_uris") or {}).get("normal"),
        "artist": card.get("artist"),
        "power": card.get("power"),
        "toughness": card.get("toughness"),
    }


def card_info(oracle_id, card):
    return {
        "id": oracle_id,
        **card_face(card),
        "faces": [card_face(face) for face in (card.get("card_faces") or [])],
    }


@router.get("/api/cards/search")
def search(q: str = Query(min_length=1, max_length=500), page: int = Query(default=1, ge=1)):
    global last_request
    key = (q.strip(), page)
    with lock:
        now = time.monotonic()
        if key in cache and cache[key][0] > now:
            return cache[key][1]
        time.sleep(max(0, last_request + 0.11 - now))
        last_request = time.monotonic()
        try:
            response = httpx.get("https://api.scryfall.com/cards/search", params={"q": key[0], "page": page},
                                 headers={"User-Agent": "UrzasWorkshop/1.0", "Accept": "application/json"}, timeout=10)
            if response.status_code in (400, 404):
                data = {}
            else:
                data = response.raise_for_status().json()
            cards = []
            for card in data.get("data", []):
                if not card.get("oracle_id"):
                    continue
                faces = card.get("card_faces") or [{}]
                images = card.get("image_uris") or faces[0].get("image_uris", {})
                cards.append({"id": card["oracle_id"], "name": card["name"], "type": card["type_line"],
                              "image": images.get("small"), "info": card_info(card["oracle_id"], card)})
            result = {"cards": cards, "total": data.get("total_cards", 0), "more": data.get("has_more", False)}
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "Kortų paieška laikinai neveikia. Bandykite vėliau.") from None
        cache[key] = (time.monotonic() + 300, result)
        cache.move_to_end(key)
        if len(cache) > 128:
            cache.popitem(last=False)
        return result


@router.get("/api/cards/{oracle_id}")
def details(oracle_id: UUID, catalog: CardCatalog = Depends(get_card_catalog)):
    card_id = str(oracle_id)
    try:
        cards = catalog.payloads_for({card_id}, [
            "name", "type_line", "mana_cost", "oracle_text", "image_url", "card_faces",
            "artist", "power", "toughness",
        ])
    except CardCatalogUnavailable:
        raise HTTPException(503, "Kortų katalogas laikinai nepasiekiamas.") from None
    if card_id not in cards:
        raise HTTPException(404, "Kortos informacija nerasta.")
    return card_info(card_id, cards[card_id])
