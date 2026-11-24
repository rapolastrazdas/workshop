import gzip
import json
from uuid import UUID

import httpx
import pytest

from app.catalog_update import download_cards, sync_catalog


CARD_ID = str(UUID(int=22))
DUMP_URL = "https://data.scryfall.io/example"
UPDATED = "2026-11-24T10:00:00+00:00"


@pytest.mark.parametrize("compressed", [True, False])
def test_import_normalizes_cards_from_current_and_legacy_dumps(compressed):
    card = {
        "oracle_id": CARD_ID, "name": "Spell // Shore", "cmc": 2,
        "type_line": "Instant // Land", "color_identity": ["U", "R"],
        "card_faces": [
            {"name": "Spell", "colors": ["U"], "mana_cost": "{1}{U}"},
            {"name": "Shore", "image_uris": {"normal": "https://example.com/shore.jpg"}},
        ],
    }
    content = gzip.compress(json.dumps(card).encode() + b"\n") if compressed else json.dumps([card]).encode()
    url_field = "jsonl_download_uri" if compressed else "download_uri"
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))) as source:
        cards = download_cards(source, {url_field: DUMP_URL})
    assert list(cards) == [CARD_ID]
    result = cards[CARD_ID]
    assert result["name_keys"] == ["spell", "spell // shore"]
    assert result["colors"] == ["U"]
    assert result["cmc"] == 2
    assert result["card_faces"][0]["mana_cost"] == "{1}{U}"
    assert result["card_faces"][1]["image_url"] == "https://example.com/shore.jpg"


def test_same_revision_skips_download_and_database_writes():
    def source_response(request):
        assert request.url.path == "/bulk-data"
        return httpx.Response(200, json={"data": [
            {"type": "oracle_cards", "updated_at": UPDATED, "jsonl_download_uri": DUMP_URL},
        ]})

    def db_response(request):
        assert request.method == "GET"
        if request.url.path == "/aliases":
            result = {"aliases": [{"alias_name": "cards", "collection_name": "active"}]}
        else:
            assert request.url.path == "/collections/active"
            result = {"config": {"metadata": {"scryfall_updated_at": UPDATED}}}
        return httpx.Response(200, json={"result": result})

    with httpx.Client(transport=httpx.MockTransport(source_response)) as source:
        with httpx.Client(base_url="http://qdrant", transport=httpx.MockTransport(db_response)) as db:
            sync_catalog(source, db, "cards")
