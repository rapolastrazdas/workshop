import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, make_engine
from app.main import app


@pytest.fixture
def client():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(app) as http:
            yield http, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
