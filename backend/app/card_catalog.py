import os
from urllib.parse import quote

import httpx

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


def get_card_catalog() -> CardCatalog:
    return CardCatalog()
