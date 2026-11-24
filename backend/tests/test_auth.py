import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, fingerprint
from app.models import AuthSession, User

PASSWORD = "TvirtasSlaptazodis9!"


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
