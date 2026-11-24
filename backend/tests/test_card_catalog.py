import json
from uuid import UUID

import httpx
import pytest

from app.card_catalog import CardCatalog, CardCatalogUnavailable


def mock_catalog(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr("app.card_catalog.httpx.Client", lambda **kwargs: real_client(
        transport=httpx.MockTransport(handler), **kwargs,
    ))
    return CardCatalog(base_url="http://catalog.local", collection="cards")


def test_retrieves_only_colors_in_batches_and_keeps_colorless_points(monkeypatch):
    ids = {str(UUID(int=n)) for n in range(1, 301)}
    batches = []

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/collections/cards/points"
        assert body["with_vector"] is False
        assert body["with_payload"] == ["colors"]
        batches.append(body["ids"])
        return httpx.Response(200, json={"result": [
            {"id": oracle_id, "payload": {"colors": [] if oracle_id.endswith("1") else ["G", "W", "G"]}}
            for oracle_id in body["ids"]
        ]})

    catalog = mock_catalog(monkeypatch, handler)
    colors = catalog.colors_for(ids)
    assert [len(batch) for batch in batches] == [256, 44]
    assert set(colors) == ids
    assert colors[str(UUID(int=1))] == []
    assert colors[str(UUID(int=2))] == ["W", "G"]


def test_missing_collection_and_missing_metadata_are_unknown(monkeypatch):
    catalog = mock_catalog(monkeypatch, lambda _: httpx.Response(404))
    assert catalog.colors_for({str(UUID(int=1))}) == {}
    assert catalog.colors_for(set()) == {}


def test_full_card_name_takes_priority_over_front_face_alias(monkeypatch):
    original, other = str(UUID(int=1)), str(UUID(int=2))
    catalog = mock_catalog(monkeypatch, lambda _: httpx.Response(200, json={"result": {
        "points": [
            {"id": original, "payload": {"name": "Lightning Bolt", "name_keys": ["lightning bolt"]}},
            {"id": other, "payload": {
                "name": "Lightning Bolt // Lightning Bolt",
                "name_keys": ["lightning bolt", "lightning bolt // lightning bolt"],
            }},
        ],
        "next_page_offset": None,
    }}))
    assert catalog.find_by_names({"lightning bolt", "lightning bolt // lightning bolt"}) == {
        "lightning bolt": original, "lightning bolt // lightning bolt": other,
    }


@pytest.mark.parametrize("status", [429, 500, 503])
def test_catalog_errors_are_reported(monkeypatch, status):
    catalog = mock_catalog(monkeypatch, lambda _: httpx.Response(status))
    with pytest.raises(CardCatalogUnavailable):
        catalog.colors_for({str(UUID(int=1))})


def test_name_lookup_scrolls_pages_and_rejects_ambiguous_aliases(monkeypatch):
    first, second = str(UUID(int=10)), str(UUID(int=11))
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.path == "/collections/cards/points/scroll"
        assert body["with_vector"] is False
        if "offset" not in body:
            return httpx.Response(200, json={"result": {"points": [
                {"id": first, "payload": {"name_keys": ["lightning bolt", "shared"]}},
            ], "next_page_offset": first}})
        return httpx.Response(200, json={"result": {"points": [
            {"id": second, "payload": {"name_keys": ["fable", "shared"]}},
        ], "next_page_offset": None}})

    catalog = mock_catalog(monkeypatch, handler)
    assert catalog.find_by_names({"lightning bolt", "fable", "shared"}) == {"lightning bolt": first, "fable": second}
    assert len(calls) == 2
