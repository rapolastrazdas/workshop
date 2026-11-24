from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app import database


def test_migration_creates_model_schema_and_can_run_again(tmp_path, monkeypatch):
    engine = database.make_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    monkeypatch.setattr(database, "engine", engine)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == {"users", "auth_sessions", "decks", "deck_cards", "alembic_version"}
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), database.Base.metadata) == []
    engine.dispose()
