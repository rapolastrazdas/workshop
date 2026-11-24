from uuid import UUID

import pytest
from sqlalchemy import select

from app.card_catalog import CardCatalogUnavailable, get_card_catalog
from app.card_import import card_name_keys, normalize_card_name
from app.main import app
from app.models import Deck, DeckCard

BOLT, FABLE = [str(UUID(int=n)) for n in [10, 11]]


class Catalog:
    def find_by_names(self, names):
        aliases = {"lightning bolt": BOLT, "fable of the mirror-breaker": FABLE,
                   "fable of the mirror-breaker // reflection of kiki": FABLE}
        return {name: aliases[name] for name in names if name in aliases}

    def colors_for(self, ids):
        return {oracle_id: ["R"] for oracle_id in ids}


@pytest.fixture
def account(client):
    http, factory = client
    result = http.post("/api/auth/register", json={
        "email": "builder@example.com", "password": "Password123!", "password_confirmation": "Password123!",
    }).json()
    app.dependency_overrides[get_card_catalog] = Catalog
    return http, factory, {"Authorization": f"Bearer {result['access_token']}"}, result["user"]["id"]


def test_named_deck_is_saved_owned_and_visible(account):
    http, factory, headers, user_id = account
    response = http.post("/api/decks", headers=headers, json={"name": "  Hues & Clues  "})
    assert response.status_code == 201
    deck = response.json()["deck"]
    assert deck["name"] == "Hues & Clues"
    assert deck["card_count"] == 0
    assert response.json()["import_result"] is None
    with factory() as db:
        assert db.get(Deck, deck["id"]).user_id == user_id
    assert http.get("/api/decks", headers=headers).json() == {"count": 1, "decks": [deck]}
    assert http.get(f"/api/decks/{deck['id']}", headers=headers).json() == deck


def test_automatic_names_count_owned_decks_and_skip_collisions(account):
    http, _, headers, _ = account
    first = http.post("/api/decks", headers=headers, json={}).json()["deck"]
    assert first["name"] == "Nauja kaladė 1"
    second = http.post("/api/decks", headers=headers, json={"name": "Nauja kaladė 3"}).json()["deck"]
    third = http.post("/api/decks", headers=headers, json={"name": "  "}).json()["deck"]
    assert second["name"] == "Nauja kaladė 3"
    assert third["name"] == "Nauja kaladė 4"


def test_name_limit_uses_unicode_characters_and_rejects_without_saving(account):
    http, factory, headers, _ = account
    assert http.post("/api/decks", headers=headers, json={"name": "ą" * 100}).status_code == 201
    response = http.post("/api/decks", headers=headers, json={"name": "ą" * 101})
    assert response.status_code == 422
    assert "name" in response.json()["detail"]["errors"]
    with factory() as db:
        assert len(db.scalars(select(Deck)).all()) == 1


def test_creation_and_import_require_authentication(client):
    http, _ = client
    assert http.post("/api/decks", json={}).status_code == 401
    assert http.post("/api/decks/1/import", json={"card_list": "Lightning Bolt"}).status_code == 401


def test_list_formats_duplicates_maybeboard_and_double_faces(account):
    http, factory, headers, _ = account
    text = "4 Lightning Bolt\n2x LIGHTNING BOLT\nFable of the Mirror-Breaker\n1 Fable of the Mirror-Breaker // Reflection of Kiki\n\nSvarstomos\nLightning Bolt"
    response = http.post("/api/decks", headers=headers, json={"card_list": text})
    assert response.status_code == 201
    data = response.json()
    assert data["deck"]["card_count"] == 8
    assert data["deck"]["colors"] == ["R"]
    assert data["import_result"] == {"imported": 9, "unrecognized_lines": [], "skipped_main": 0}
    with factory() as db:
        rows = {(row.oracle_id, row.list_name): row.quantity for row in db.scalars(select(DeckCard))}
        assert rows == {(BOLT, "main"): 6, (FABLE, "main"): 2, (BOLT, "maybeboard"): 1}


def test_unrecognized_lines_remain_separate_from_successful_import(account):
    http, _, headers, _ = account
    response = http.post("/api/decks", headers=headers, json={"card_list": "Deck\n0 Lightning Bolt\n-2 Lightning Bolt\nUnknown Card\nLightning Bolt\nMaybeboard\nUnknown Maybe"})
    assert response.status_code == 201
    result = response.json()["import_result"]
    assert result["imported"] == 1
    unknown = {(line["text"], line["list_name"]) for line in result["unrecognized_lines"]}
    assert unknown == {("Deck", "main"), ("0 Lightning Bolt", "main"), ("-2 Lightning Bolt", "main"),
                       ("Unknown Card", "main"), ("Unknown Maybe", "maybeboard")}


def test_no_recognized_lines_still_creates_empty_deck(account):
    http, _, headers, _ = account
    response = http.post("/api/decks", headers=headers, json={"card_list": "abc"})
    assert response.status_code == 201
    assert response.json()["deck"]["card_count"] == 0
    assert response.json()["import_result"]["imported"] == 0


def test_main_limit_partial_import_and_retry_adds_only_available_space(account):
    http, factory, headers, _ = account
    response = http.post("/api/decks", headers=headers, json={"card_list": "499 Lightning Bolt\n3 Fable of the Mirror-Breaker\nMaybeboard\n600 Lightning Bolt"})
    data = response.json()
    assert data["deck"]["card_count"] == 500
    assert data["import_result"]["skipped_main"] == 2
    assert data["import_result"]["imported"] == 1100
    retry = http.post(f"/api/decks/{data['deck']['id']}/import", headers=headers, json={"card_list": "Lightning Bolt\nMaybeboard\n2 Lightning Bolt"})
    assert retry.status_code == 200
    assert retry.json()["deck"]["card_count"] == 500
    assert retry.json()["import_result"]["skipped_main"] == 1
    assert retry.json()["import_result"]["imported"] == 2
    with factory() as db:
        row = db.get(DeckCard, (data["deck"]["id"], BOLT, "maybeboard"))
        assert row.quantity == 602


def test_corrected_import_accumulates_in_existing_deck(account):
    http, _, headers, _ = account
    data = http.post("/api/decks", headers=headers, json={"card_list": "Lightning Bolt\nabc"}).json()
    retry = http.post(f"/api/decks/{data['deck']['id']}/import", headers=headers, json={"card_list": "2x Lightning Bolt"})
    assert retry.status_code == 200
    assert retry.json()["deck"]["card_count"] == 3
    assert retry.json()["import_result"]["imported"] == 2


def test_foreign_import_cannot_modify_deck(account):
    http, factory, headers, _ = account
    other = http.post("/api/auth/register", json={"email": "other@example.com", "password": "Password123!", "password_confirmation": "Password123!"}).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    deck = http.post("/api/decks", headers=other_headers, json={}).json()["deck"]
    response = http.post(f"/api/decks/{deck['id']}/import", headers=headers, json={"card_list": "Lightning Bolt"})
    assert response.status_code == 404
    with factory() as db:
        assert db.scalars(select(DeckCard)).all() == []


def test_catalog_failure_rolls_back_creation(account):
    http, factory, headers, _ = account

    class Unavailable(Catalog):
        def find_by_names(self, _):
            raise CardCatalogUnavailable

    app.dependency_overrides[get_card_catalog] = Unavailable
    response = http.post("/api/decks", headers=headers, json={"card_list": "Lightning Bolt"})
    assert response.status_code == 503
    with factory() as db:
        assert db.scalars(select(Deck)).all() == []
        assert db.scalars(select(DeckCard)).all() == []


def test_name_normalization_and_double_face_alias_contract():
    assert normalize_card_name("  Urza’s,   SAGA ") == "urzas saga"
    assert card_name_keys("Fable of the Mirror-Breaker // Reflection of Kiki") == [
        "fable of the mirror-breaker", "fable of the mirror-breaker // reflection of kiki",
    ]


def test_printing_suffix_is_accepted_during_creation_and_settings_import(account):
    http, factory, headers, _ = account
    response = http.post("/api/decks", headers=headers, json={"card_list": "2 Lightning Bolt (M10) 146\n1x LIGHTNING BOLT (A25) 141"})
    assert response.status_code == 201
    deck = response.json()["deck"]
    assert deck["card_count"] == 3
    assert response.json()["import_result"]["unrecognized_lines"] == []
    updated = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "Printing import", "card_list": "Lightning Bolt (M10) 146\nMaybeboard\n2 Lightning Bolt (A25) 141"})
    assert updated.status_code == 200
    assert updated.json()["deck"]["card_count"] == 4
    assert updated.json()["import_result"]["imported"] == 3
    with factory() as db:
        assert db.get(DeckCard, (deck["id"], BOLT, "main")).quantity == 4
        assert db.get(DeckCard, (deck["id"], BOLT, "maybeboard")).quantity == 2
