from uuid import UUID

import pytest
from sqlalchemy import delete, select

from app.card_catalog import CardCatalogUnavailable, get_card_catalog
from app.main import app
from app.models import Deck, DeckCard

WHITE, MULTI, COLORLESS, RED = [str(UUID(int=n)) for n in range(1, 5)]


class Catalog:
    def __init__(self):
        self.requested = set()
        self.colors = {WHITE: ["W"], MULTI: ["B", "U"], COLORLESS: [], RED: ["R"]}

    def colors_for(self, ids):
        self.requested.update(ids)
        return {key: value for key, value in self.colors.items() if key in ids}


def register(http, email):
    response = http.post("/api/auth/register", json={
        "email": email, "password": "Password123!", "password_confirmation": "Password123!",
    })
    assert response.status_code == 201
    account = response.json()
    return account["user"]["id"], {"Authorization": f"Bearer {account['access_token']}"}


@pytest.fixture
def decks_data(client):
    http, factory = client
    owner, headers = register(http, "owner@example.com")
    other, other_headers = register(http, "other@example.com")
    with factory() as db:
        decks = [
            Deck(user_id=owner, name="Main deck"), Deck(user_id=owner, name="Empty"),
            Deck(user_id=owner, name="Colorless"), Deck(user_id=owner, name="Maybeboard only"),
            Deck(user_id=other, name="Private deck"),
        ]
        db.add_all(decks)
        db.flush()
        ids = [deck.id for deck in decks]
        db.add_all([
            DeckCard(deck_id=ids[0], oracle_id=WHITE, list_name="main", quantity=4),
            DeckCard(deck_id=ids[0], oracle_id=MULTI, list_name="main", quantity=2),
            DeckCard(deck_id=ids[0], oracle_id=COLORLESS, list_name="main", quantity=1),
            DeckCard(deck_id=ids[0], oracle_id=WHITE, list_name="maybeboard", quantity=20),
            DeckCard(deck_id=ids[0], oracle_id=RED, list_name="maybeboard", quantity=99),
            DeckCard(deck_id=ids[2], oracle_id=COLORLESS, list_name="main", quantity=3),
            DeckCard(deck_id=ids[3], oracle_id=RED, list_name="maybeboard", quantity=2),
            DeckCard(deck_id=ids[4], oracle_id=RED, list_name="main", quantity=50),
        ])
        db.commit()
    catalog = Catalog()
    app.dependency_overrides[get_card_catalog] = lambda: catalog
    return http, factory, headers, other_headers, ids, catalog


def test_empty_account_gets_zero_decks(client):
    http, _ = client
    _, headers = register(http, "empty@example.com")
    response = http.get("/api/decks", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"count": 0, "decks": []}


def test_only_owned_decks_with_main_card_quantities_and_colors(decks_data):
    http, _, headers, _, ids, catalog = decks_data
    response = http.get("/api/decks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    assert [deck["id"] for deck in data["decks"]] == list(reversed(ids[:4]))
    by_name = {deck["name"]: deck for deck in data["decks"]}
    assert by_name["Main deck"]["card_count"] == 7
    assert by_name["Main deck"]["colors"] == ["W", "U", "B"]
    assert by_name["Main deck"]["colors_known"] is True
    assert by_name["Empty"]["card_count"] == 0
    assert by_name["Empty"]["colors"] == []
    assert by_name["Colorless"]["card_count"] == 3
    assert by_name["Colorless"]["colors"] == []
    assert by_name["Colorless"]["colors_known"] is True
    assert by_name["Maybeboard only"]["card_count"] == 0
    assert by_name["Maybeboard only"]["colors"] == []
    assert catalog.requested == {WHITE, MULTI, COLORLESS}
    assert "user_id" not in response.text
    assert "Private deck" not in response.text


def test_own_deck_opens_and_other_users_deck_is_indistinguishable_from_missing(decks_data):
    http, _, headers, other_headers, ids, catalog = decks_data
    response = http.get(f"/api/decks/{ids[0]}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Main deck"
    assert response.json()["card_count"] == 7
    catalog.requested.clear()
    foreign = http.get(f"/api/decks/{ids[4]}", headers=headers)
    missing = http.get("/api/decks/2147483647", headers=headers)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Kaladė nerasta."}
    assert catalog.requested == set()
    assert http.get(f"/api/decks/{ids[0]}", headers=other_headers).status_code == 404


@pytest.mark.parametrize("deck_id", ["invalid", "-1", "0", "999999999999999999999999", "1.5"])
def test_invalid_deck_address_returns_not_found(decks_data, deck_id):
    http, _, headers, _, _, _ = decks_data
    response = http.get(f"/api/decks/{deck_id}", headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Kaladė nerasta."}


def test_missing_metadata_does_not_claim_colorless(decks_data):
    http, _, headers, _, ids, catalog = decks_data
    catalog.colors = {}
    response = http.get(f"/api/decks/{ids[0]}", headers=headers)
    assert response.status_code == 200
    assert response.json()["card_count"] == 7
    assert response.json()["colors_known"] is False


def test_catalog_failure_is_retryable_not_a_false_empty_list(decks_data):
    http, _, headers, _, _, catalog = decks_data

    def unavailable(_):
        raise CardCatalogUnavailable

    catalog.colors_for = unavailable
    response = http.get("/api/decks", headers=headers)
    assert response.status_code == 503
    assert "Bandykite dar kartą" in response.json()["detail"]


def test_deleting_deck_cascades_to_its_composition_only(decks_data):
    _, factory, _, _, ids, _ = decks_data
    with factory() as db:
        db.execute(delete(Deck).where(Deck.id == ids[0]))
        db.commit()
        assert db.scalars(select(DeckCard).where(DeckCard.deck_id == ids[0])).all() == []
        assert len(db.scalars(select(DeckCard)).all()) == 3
