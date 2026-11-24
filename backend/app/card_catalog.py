import os
from urllib.parse import quote
from uuid import UUID

import httpx

from .card_import import card_name_keys, normalize_card_name

MANA_COLORS = ("W", "U", "B", "R", "G")


class CardCatalogUnavailable(Exception):
    pass


class CardCatalog:
    """Read public card metadata by Oracle ID; deck ownership stays in PostgreSQL."""

    def __init__(self, base_url: str | None = None, collection: str | None = None):
        self.base_url = base_url or os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
        self.collection = collection or os.getenv("QDRANT_CARDS_COLLECTION", "cards")

    def colors_for(self, oracle_ids: set[str]) -> dict[str, list[str]]:
        if not oracle_ids:
            return {}
        ids = sorted(oracle_ids)
        result = {}
        try:
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                for offset in range(0, len(ids), 256):
                    response = client.post(
                        f"/collections/{quote(self.collection, safe='')}/points",
                        json={"ids": ids[offset:offset + 256], "with_payload": ["colors"], "with_vector": False},
                    )
                    # Before NI-23 imports cards there may be no collection yet.
                    if response.status_code == 404:
                        return {}
                    response.raise_for_status()
                    for point in response.json()["result"]:
                        colors = (point.get("payload") or {}).get("colors")
                        if isinstance(colors, list) and all(color in MANA_COLORS for color in colors):
                            result[str(point["id"])] = [color for color in MANA_COLORS if color in colors]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise CardCatalogUnavailable from error
        return result

    def find_by_names(self, names: set[str]) -> dict[str, str]:
        if not names:
            return {}
        exact_matches: dict[str, set[str]] = {}
        alias_matches: dict[str, set[str]] = {}
        keys = sorted(names)
        try:
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                for start in range(0, len(keys), 128):
                    requested = set(keys[start:start + 128])
                    offset = None
                    while True:
                        body = {
                            "filter": {"must": [{"key": "name_keys", "match": {"any": sorted(requested)}}]},
                            "limit": 256, "with_payload": ["name", "name_keys"], "with_vector": False,
                        }
                        if offset is not None:
                            body["offset"] = offset
                        response = client.post(f"/collections/{quote(self.collection, safe='')}/points/scroll", json=body)
                        if response.status_code == 404:
                            return {}
                        response.raise_for_status()
                        page = response.json()["result"]
                        for point in page["points"]:
                            oracle_id = str(UUID(str(point["id"])))
                            payload = point.get("payload") or {}
                            name = payload.get("name", "")
                            exact = normalize_card_name(name)
                            aliases = payload.get("name_keys") or card_name_keys(name)
                            for key in requested.intersection(aliases):
                                matches = exact_matches if key == exact else alias_matches
                                matches.setdefault(key, set()).add(oracle_id)
                        offset = page.get("next_page_offset")
                        if offset is None:
                            break
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise CardCatalogUnavailable from error
        preferred = {**alias_matches, **exact_matches}
        return {key: next(iter(ids)) for key, ids in preferred.items() if len(ids) == 1}


def get_card_catalog() -> CardCatalog:
    return CardCatalog()
