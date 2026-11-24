import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, make_engine
from app.main import app, fingerprint
from app.models import AuthSession, Deck, User

PASSWORD = "TvirtasSlaptazodis9!"


@pytest.fixture
def client():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as http:
        yield http, factory
    app.dependency_overrides.clear()
    engine.dispose()


def register(http, email="player@example.com", password=PASSWORD):
    return http.post("/api/auth/register", json={
        "email": email, "password": password, "password_confirmation": password,
    })


def header(token):
    return {"Authorization": f"Bearer {token}"}


def test_registration_signs_in_and_stores_only_hashes(client):
    http, factory = client
    response = register(http, " Player@Example.com ")
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "player@example.com"
    assert data["expires_at"] > time.time()
    assert "password" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert http.get("/api/auth/me", headers=header(data["access_token"])).json() == data["user"]
    with factory() as db:
        user = db.scalar(select(User))
        session = db.scalar(select(AuthSession))
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert session.token_hash == fingerprint(data["access_token"])
        assert session.token_hash != data["access_token"]


def test_all_field_errors_do_not_create_account(client):
    http, factory = client
    response = http.post("/api/auth/register", json={
        "email": "not-an-email", "password": "12345678", "password_confirmation": "different",
    })
    assert response.status_code == 422
    assert set(response.json()["detail"]["errors"]) == {"email", "password", "password_confirmation"}
    with factory() as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(AuthSession)) is None


def test_password_strictly_longer_than_eight(client):
    http, _ = client
    assert register(http, password="12345678").status_code == 422
    assert register(http, password="123456789").status_code == 201


def test_duplicate_email_case_insensitive(client):
    http, factory = client
    assert register(http).status_code == 201
    response = register(http, "PLAYER@example.com")
    assert response.status_code == 409
    assert response.json()["detail"]["errors"]["email"] == "Šis el. paštas jau užregistruotas."
    with factory() as db:
        assert len(db.scalars(select(User)).all()) == 1


def test_login_uniform_failure(client):
    http, _ = client
    register(http)
    failures = []
    for email, password in [("player@example.com", "wrong"), ("unknown@example.com", PASSWORD), ("invalid", PASSWORD)]:
        result = http.post("/api/auth/login", json={"email": email, "password": password})
        assert result.status_code == 401
        failures.append(result.json())
    assert failures[0] == failures[1] == failures[2]
    result = http.post("/api/auth/login", json={"email": "PLAYER@example.com", "password": PASSWORD})
    assert result.status_code == 200
    assert http.get("/api/auth/me", headers=header(result.json()["access_token"])).status_code == 200


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/decks", "/api/decks/123"])
def test_private_endpoints_reject_guests_and_forged_tokens(client, path):
    http, _ = client
    assert http.get(path).status_code == 401
    assert http.get(path, headers=header("forged-token")).status_code == 401


def test_logout_revokes_only_current_token(client):
    http, _ = client
    first = register(http).json()["access_token"]
    second = http.post("/api/auth/login", json={"email": "player@example.com", "password": PASSWORD}).json()["access_token"]
    assert http.post("/api/auth/logout", headers=header(first)).status_code == 204
    assert http.get("/api/auth/me", headers=header(first)).status_code == 401
    assert http.get("/api/decks", headers=header(second)).status_code == 200
    assert http.post("/api/auth/logout", headers=header(first)).status_code == 401


def test_expired_token_rejected(client):
    http, factory = client
    token = register(http).json()["access_token"]
    with factory() as db:
        session = db.get(AuthSession, fingerprint(token))
        session.expires_at = int(time.time()) - 1
        db.commit()
    for path in ["/api/auth/me", "/api/decks", "/api/decks/1"]:
        response = http.get(path, headers=header(token))
        assert response.status_code == 401
        assert "sesija baigėsi" in response.json()["detail"]
    assert http.post("/api/auth/logout", headers=header(token)).status_code == 401


@pytest.mark.parametrize("password", ["wrong-password", "", "x" * 1025])
def test_account_wrong_password_preserves_all_data(client, password):
    http, factory = client
    account = register(http).json()
    with factory() as db:
        db.add(Deck(user_id=account["user"]["id"], name="Keep this deck"))
        db.commit()
    response = http.request("DELETE", "/api/auth/account", headers=header(account["access_token"]), json={"password": password})
    assert response.status_code == 403
    assert response.json()["detail"]["errors"]["password"] == "Neteisingas slaptažodis."
    with factory() as db:
        assert db.get(User, account["user"]["id"]) is not None
        assert len(db.scalars(select(Deck)).all()) == 1
        assert len(db.scalars(select(AuthSession)).all()) == 1
    assert http.get("/api/auth/me", headers=header(account["access_token"])).status_code == 200


def test_account_deletion_removes_decks_and_all_sessions_only_for_owner(client):
    http, factory = client
    account = register(http).json()
    second_token = http.post("/api/auth/login", json={"email": account["user"]["email"], "password": PASSWORD}).json()["access_token"]
    other = register(http, "other@example.com").json()
    with factory() as db:
        db.add_all([
            Deck(user_id=account["user"]["id"], name="First deck"),
            Deck(user_id=account["user"]["id"], name="Second deck"),
            Deck(user_id=other["user"]["id"], name="Other player's deck"),
        ])
        db.commit()
    # A submitted user ID cannot redirect deletion to somebody else's account.
    response = http.request("DELETE", "/api/auth/account", headers=header(account["access_token"]),
                            json={"password": PASSWORD, "user_id": other["user"]["id"]})
    assert response.status_code == 204
    with factory() as db:
        assert db.get(User, account["user"]["id"]) is None
        assert db.get(User, other["user"]["id"]) is not None
        assert [deck.user_id for deck in db.scalars(select(Deck))] == [other["user"]["id"]]
        assert [session.user_id for session in db.scalars(select(AuthSession))] == [other["user"]["id"]]
    for token in [account["access_token"], second_token]:
        assert http.get("/api/auth/me", headers=header(token)).status_code == 401
        assert http.get("/api/decks", headers=header(token)).status_code == 401
    assert http.get("/api/auth/me", headers=header(other["access_token"])).status_code == 200
    assert http.post("/api/auth/login", json={"email": account["user"]["email"], "password": PASSWORD}).status_code == 401
    # No account record remains reserving the old email.
    assert register(http).status_code == 201


@pytest.mark.parametrize("credential", ["missing", "forged", "expired"])
def test_account_deletion_requires_valid_session(client, credential):
    http, factory = client
    account = register(http).json()
    if credential == "expired":
        with factory() as db:
            db.get(AuthSession, fingerprint(account["access_token"])).expires_at = int(time.time()) - 1
            db.commit()
    headers = {} if credential == "missing" else header(account["access_token"] if credential == "expired" else "fake")
    response = http.request("DELETE", "/api/auth/account", headers=headers, json={"password": PASSWORD})
    assert response.status_code == 401
    with factory() as db:
        assert db.get(User, account["user"]["id"]) is not None


def test_account_deletion_rolls_back_when_transaction_fails(client):
    http, factory = client
    account = register(http).json()
    with factory() as db:
        db.add(Deck(user_id=account["user"]["id"], name="Keep after rollback"))
        db.commit()

    def fail_after_delete(db):
        db.flush()
        raise RuntimeError("Simulated commit failure")

    event.listen(factory.class_, "before_commit", fail_after_delete)
    try:
        with pytest.raises(RuntimeError, match="Simulated commit failure"):
            http.request("DELETE", "/api/auth/account", headers=header(account["access_token"]), json={"password": PASSWORD})
    finally:
        event.remove(factory.class_, "before_commit", fail_after_delete)
    with factory() as db:
        assert db.get(User, account["user"]["id"]) is not None
        assert len(db.scalars(select(Deck)).all()) == 1
        assert len(db.scalars(select(AuthSession)).all()) == 1
