import time
from collections import OrderedDict
from threading import Lock

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
cache = OrderedDict()
lock = Lock()
last_request = 0.0


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
                faces = card.get("card_faces") or [{}]
                images = card.get("image_uris") or faces[0].get("image_uris", {})
                cards.append({"id": card["oracle_id"], "name": card["name"], "type": card["type_line"],
                              "image": images.get("small")})
            result = {"cards": cards, "total": data.get("total_cards", 0), "more": data.get("has_more", False)}
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "Kortų paieška laikinai neveikia. Bandykite vėliau.") from None
        cache[key] = (time.monotonic() + 300, result)
        cache.move_to_end(key)
        if len(cache) > 128:
            cache.popitem(last=False)
        return result
