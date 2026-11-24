from uuid import UUID

import pytest
from sqlalchemy import select

from app.card_catalog import CardCatalogUnavailable, get_card_catalog
from app.main import app, fingerprint
from app.models import AuthSession, Deck, DeckCard

BOLT, BLUE = str(UUID(int=10)), str(UUID(int=12))


class Catalog:
    def find_by_names(self, names):
        ids = {"lightning bolt": BOLT, "blue draw": BLUE}
        return {name: ids[name] for name in names if name in ids}

    def colors_for(self, ids):
        return {oracle_id: ["R"] if oracle_id == BOLT else ["U"] for oracle_id in ids}

    def payloads_for(self, ids, fields):
        return {oracle_id: {"colors": colors} for oracle_id, colors in self.colors_for(ids).items()}


@pytest.fixture
def settings(client):
    http, factory = client
    account = http.post("/api/auth/register", json={
        "email": "settings@example.com", "password": "Password123!", "password_confirmation": "Password123!",
    }).json()
    app.dependency_overrides[get_card_catalog] = Catalog
    token = account["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = http.post("/api/decks", headers=headers, json={
        "name": "Original", "card_list": "2 Lightning Bolt\nMaybeboard\nLightning Bolt",
    })
    assert response.status_code == 201
    return http, factory, headers, response.json()["deck"], token


def test_rename_and_import_add_to_existing_cards_and_update_list(settings):
    http, factory, headers, deck, _ = settings
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={
        "name": "  Renamed  ", "card_list": "3 Lightning Bolt\nBlue Draw\nSvarstomos\n2 Lightning Bolt",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["deck"]["name"] == "Renamed"
    assert data["deck"]["card_count"] == 6
    assert data["deck"]["colors"] == ["U", "R"]
    assert data["import_result"]["imported"] == 6
    detail = http.get(f"/api/decks/{deck['id']}", headers=headers).json()
    cards = detail.pop("cards")
    assert detail == data["deck"]
    assert {(card["oracle_id"], card["list_name"]): card["quantity"] for card in cards} == {
        (BOLT, "main"): 5, (BLUE, "main"): 1, (BOLT, "maybeboard"): 3,
    }
    assert http.get("/api/decks", headers=headers).json()["decks"] == [data["deck"]]
    with factory() as db:
        rows = {(row.oracle_id, row.list_name): row.quantity for row in db.scalars(select(DeckCard))}
        assert rows == {(BOLT, "main"): 5, (BLUE, "main"): 1, (BOLT, "maybeboard"): 3}


@pytest.mark.parametrize("name", ["", "   ", "ą" * 101])
def test_invalid_name_preserves_name_and_composition(settings, name):
    http, factory, headers, deck, _ = settings
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": name, "card_list": "Lightning Bolt"})
    assert response.status_code == 422
    assert "name" in response.json()["detail"]["errors"]
    with factory() as db:
        assert db.get(Deck, deck["id"]).name == "Original"
        assert db.get(DeckCard, (deck["id"], BOLT, "main")).quantity == 2


def test_rename_only_accepts_100_unicode_characters_and_keeps_cards(settings):
    http, _, headers, deck, _ = settings
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "ą" * 100})
    assert response.status_code == 200
    assert response.json()["deck"]["name"] == "ą" * 100
    assert response.json()["deck"]["card_count"] == 2
    assert response.json()["import_result"] is None


def test_unknown_lines_are_reported_but_valid_rename_is_saved(settings):
    http, _, headers, deck, _ = settings
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "Renamed", "card_list": "Unknown Card"})
    assert response.status_code == 200
    assert response.json()["deck"]["name"] == "Renamed"
    assert response.json()["deck"]["card_count"] == 2
    assert response.json()["import_result"]["unrecognized_lines"] == [{"text": "Unknown Card", "list_name": "main"}]


def test_import_failure_rolls_back_rename_and_card_changes(settings):
    http, factory, headers, deck, _ = settings

    class Unavailable(Catalog):
        def find_by_names(self, _):
            raise CardCatalogUnavailable

    app.dependency_overrides[get_card_catalog] = Unavailable
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "Not saved", "card_list": "Lightning Bolt"})
    assert response.status_code == 503
    with factory() as db:
        assert db.get(Deck, deck["id"]).name == "Original"
        assert db.get(DeckCard, (deck["id"], BOLT, "main")).quantity == 2


def test_other_users_settings_are_indistinguishable_from_missing(settings):
    http, factory, _, deck, _ = settings
    other = http.post("/api/auth/register", json={"email": "other@example.com", "password": "Password123!", "password_confirmation": "Password123!"}).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    foreign = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "Not yours"})
    missing = http.put("/api/decks/2147483647", headers=headers, json={"name": "Missing"})
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    with factory() as db:
        assert db.get(Deck, deck["id"]).name == "Original"


@pytest.mark.parametrize("credential", ["missing", "forged", "expired"])
def test_settings_require_valid_session(settings, credential):
    http, factory, headers, deck, token = settings
    if credential == "missing":
        headers = {}
    elif credential == "forged":
        headers = {"Authorization": "Bearer fake"}
    else:
        with factory() as db:
            db.get(AuthSession, fingerprint(token)).expires_at = 0
            db.commit()
    response = http.put(f"/api/decks/{deck['id']}", headers=headers, json={"name": "Not saved"})
    assert response.status_code == 401
