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

    def __init__(self, base_url: str | None = None, collection: str | None = None,
                 fallback_collection: str | None = None):
        self.base_url = base_url or os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
        self.collection = collection or os.getenv("QDRANT_CARDS_COLLECTION", "cards")
        self.fallback_collection = fallback_collection

    def _post(self, client: httpx.Client, endpoint: str, body: dict) -> httpx.Response:
        response = client.post(f"/collections/{quote(self.collection, safe='')}/{endpoint}", json=body)
        if response.status_code == 404 and self.fallback_collection:
            return client.post(
                f"/collections/{quote(self.fallback_collection, safe='')}/{endpoint}", json=body,
            )
        return response

    def colors_for(self, oracle_ids: set[str]) -> dict[str, list[str]]:
        return self.colors_from(self.payloads_for(oracle_ids, ["colors"]))

    @staticmethod
    def colors_from(payloads: dict[str, dict]) -> dict[str, list[str]]:
        result = {}
        for oracle_id, payload in payloads.items():
            colors = payload.get("colors")
            if isinstance(colors, list) and all(color in MANA_COLORS for color in colors):
                result[oracle_id] = [color for color in MANA_COLORS if color in colors]
        return result

    def payloads_for(self, oracle_ids: set[str], fields: list[str]) -> dict[str, dict]:
        if not oracle_ids:
            return {}
        ids = sorted(oracle_ids)
        result = {}
        try:
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                for offset in range(0, len(ids), 256):
                    response = self._post(
                        client, "points",
                        {"ids": ids[offset:offset + 256], "with_payload": fields, "with_vector": False},
                    )
                    # Before NI-23 imports cards there may be no collection yet.
                    if response.status_code == 404:
                        return {}
                    response.raise_for_status()
                    for point in response.json()["result"]:
                        result[str(point["id"])] = point.get("payload") or {}
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
                        response = self._post(client, "points/scroll", body)
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
    legacy = os.getenv("QDRANT_CARDS_COLLECTION", "cards")
    return CardCatalog(collection=f"{legacy}__current", fallback_collection=legacy)
