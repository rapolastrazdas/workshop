from uuid import UUID

import pytest
from sqlalchemy import event, select

from app.card_catalog import get_card_catalog
from app.main import app, fingerprint
from app.models import AuthSession, Deck, DeckCard

NAME = "Hues & Clues"
MISMATCH = "Įvestas pavadinimas nesutampa su kaladės pavadinimu."


def auth(account):
    return {"Authorization": f"Bearer {account['access_token']}"}


def remove(http, deck_id, account, name=NAME):
    return http.request("DELETE", f"/api/decks/{deck_id}", headers=auth(account), json={"name": name})


@pytest.fixture
def deck_data(client):
    http, factory = client
    accounts = [http.post("/api/auth/register", json={
        "email": email, "password": "Password123!", "password_confirmation": "Password123!",
    }).json() for email in ["owner@example.com", "other@example.com"]]
    owner, other = accounts
    with factory() as db:
        decks = [Deck(user_id=owner["user"]["id"], name=NAME),
                 Deck(user_id=owner["user"]["id"], name=NAME),
                 Deck(user_id=other["user"]["id"], name=NAME)]
        db.add_all(decks)
        db.flush()
        ids = [deck.id for deck in decks]
        for deck_id in ids:
            for list_name in ["main", "maybeboard"]:
                db.add(DeckCard(deck_id=deck_id, oracle_id=str(UUID(int=1)), list_name=list_name, quantity=3))
        db.commit()

    class Catalog:
        def colors_for(self, ids):
            return {oracle_id: [] for oracle_id in ids}

    app.dependency_overrides[get_card_catalog] = Catalog
    return http, factory, owner, other, ids


@pytest.mark.parametrize("name", ["", "Hues & Clue", "hues & clues", " Hues & Clues "])
def test_mismatch_does_not_change_deck_or_cards(deck_data, name):
    http, factory, owner, _, ids = deck_data
    response = remove(http, ids[0], owner, name)
    assert response.status_code == 422
    assert response.json() == {"detail": {"errors": {"name": MISMATCH}}}
    with factory() as db:
        assert db.get(Deck, ids[0]).name == NAME
        assert len(db.scalars(select(DeckCard)).all()) == 6


def test_deletes_selected_deck_and_both_lists_but_keeps_other_decks_and_session(deck_data):
    http, factory, owner, other, ids = deck_data
    response = remove(http, ids[0], owner)
    assert response.status_code == 204
    assert response.content == b""
    with factory() as db:
        assert db.get(Deck, ids[0]) is None
        assert db.scalars(select(DeckCard).where(DeckCard.deck_id == ids[0])).all() == []
        assert db.get(Deck, ids[1]) is not None
        assert db.get(Deck, ids[2]) is not None
        assert len(db.scalars(select(DeckCard)).all()) == 4
        assert len(db.scalars(select(AuthSession)).all()) == 2
    assert http.get(f"/api/decks/{ids[0]}", headers=auth(owner)).status_code == 404
    assert http.get("/api/decks", headers=auth(owner)).json()["count"] == 1
    assert http.get("/api/auth/me", headers=auth(owner)).status_code == 200
    assert http.get("/api/decks", headers=auth(other)).json()["count"] == 1


def test_foreign_and_missing_decks_return_same_error_even_with_correct_name(deck_data):
    http, factory, owner, _, ids = deck_data
    foreign = remove(http, ids[2], owner)
    missing = remove(http, 2147483647, owner)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Kaladė nerasta."}
    with factory() as db:
        assert len(db.scalars(select(Deck)).all()) == 3


@pytest.mark.parametrize("credential", ["missing", "forged", "expired"])
def test_deletion_requires_valid_session(deck_data, credential):
    http, factory, owner, _, ids = deck_data
    headers = auth(owner)
    if credential == "missing":
        headers = {}
    elif credential == "forged":
        headers = {"Authorization": "Bearer fake"}
    else:
        with factory() as db:
            db.get(AuthSession, fingerprint(owner["access_token"])).expires_at = 0
            db.commit()
    response = http.request("DELETE", f"/api/decks/{ids[0]}", headers=headers, json={"name": NAME})
    assert response.status_code == 401
    with factory() as db:
        assert db.get(Deck, ids[0]) is not None


def test_name_is_checked_again_after_concurrent_rename(deck_data):
    http, factory, owner, _, ids = deck_data
    with factory() as db:
        db.get(Deck, ids[0]).name = "Renamed"
        db.commit()
    assert remove(http, ids[0], owner).status_code == 422
    assert remove(http, ids[0], owner, "Renamed").status_code == 204


def test_failed_commit_restores_deck_and_cards(deck_data):
    http, factory, owner, _, ids = deck_data

    def fail_after_delete(db):
        db.flush()
        raise RuntimeError("Simulated deletion failure")

    event.listen(factory.class_, "before_commit", fail_after_delete)
    try:
        with pytest.raises(RuntimeError, match="Simulated deletion failure"):
            remove(http, ids[0], owner)
    finally:
        event.remove(factory.class_, "before_commit", fail_after_delete)
    with factory() as db:
        assert db.get(Deck, ids[0]) is not None
        assert len(db.scalars(select(DeckCard)).all()) == 6
