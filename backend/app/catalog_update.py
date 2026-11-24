"""Import the Scryfall Oracle Cards dump into a versioned Qdrant collection."""

import argparse
import gzip
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from itertools import batched
from typing import Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import ijson

from .card_catalog import get_card_catalog
from .card_import import card_name_keys

LOG = logging.getLogger(__name__)
BATCH_SIZE = 256
DAILY_SECONDS = 24 * 60 * 60
SCRYFALL_BULK = "https://api.scryfall.com/bulk-data"
SCRYFALL_HEADERS = {"User-Agent": "UrzasWorkshop/0.1", "Accept": "application/json"}


class CardEncoder(Protocol):
    """NI-25 supplies the version, Qdrant vector schema and encoded states."""

    version: str
    vector_config: dict

    def encode(self, payload: dict) -> dict:
        ...


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Scryfall update timestamp has no time zone")
    return parsed


def card_fields(card: dict) -> dict:
    return {
        "name": card["name"],
        "type_line": card.get("type_line") or "",
        "mana_cost": card.get("mana_cost") or "",
        "oracle_text": card.get("oracle_text") or "",
        "image_url": (card.get("image_uris") or {}).get("normal"),
    }


def dump_records(dump, *, jsonl: bool):
    if jsonl:
        compressed = dump.read(2) == b"\x1f\x8b"
        dump.seek(0)
        if compressed:
            with gzip.GzipFile(fileobj=dump) as stream:
                yield from (json.loads(line) for line in stream if line.strip())
        else:
            yield from (json.loads(line) for line in dump if line.strip())
        return
    if not dump.read(4096).lstrip().startswith(b"["):
        raise ValueError("Expected a Scryfall JSON array")
    dump.seek(0)
    yield from ijson.items(dump, "item", use_float=True)


def download_cards(source: httpx.Client, descriptor: dict) -> dict[str, dict]:
    jsonl_url = descriptor.get("jsonl_download_uri")
    url = jsonl_url or descriptor["download_uri"]
    cards = {}
    skipped = 0
    with tempfile.TemporaryFile() as dump:
        with source.stream("GET", url) as response:
            response.raise_for_status()
            for block in response.iter_bytes(chunk_size=256 * 1024):
                dump.write(block)
        dump.seek(0)
        for card in dump_records(dump, jsonl=bool(jsonl_url)):
            # Some special game objects have no Oracle ID.
            if not card.get("oracle_id"):
                skipped += 1
                continue
            card_id = str(UUID(card["oracle_id"]))
            payload = card_fields(card)
            faces = [card_fields(face) for face in card.get("card_faces", [])]
            payload.update(
                name_keys=card_name_keys(payload["name"]),
                colors=card.get("colors", sorted({
                    color for face in card.get("card_faces", []) for color in face.get("colors", [])
                })),
                cmc=card.get("cmc"),
                card_faces=faces,
            )
            if card_id in cards:
                raise ValueError(f"Duplicate Oracle ID: {card_id}")
            cards[card_id] = payload
    if not cards:
        raise ValueError("Scryfall dump contains no Oracle cards")
    if skipped:
        LOG.warning("Skipped %d objects without an Oracle ID", skipped)
    return cards


def request(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.is_error:
        LOG.error("Qdrant %s %s: %s", method, path, response.text[:500])
    response.raise_for_status()
    return response.json()["result"]


def aliases(db: httpx.Client) -> dict[str, str]:
    return {
        row["alias_name"]: row["collection_name"]
        for row in request(db, "GET", "/aliases")["aliases"]
    }


def old_batches(db: httpx.Client, path: str, with_vectors: bool):
    offset = None
    while True:
        query = {"limit": BATCH_SIZE, "with_payload": True, "with_vector": with_vectors}
        if offset is not None:
            query["offset"] = offset
        page = request(db, "POST", f"{path}/points/scroll", json=query)
        yield page["points"]
        offset = page["next_page_offset"]
        if offset is None:
            break


def make_point(card_id: str, payload: dict, encoder: CardEncoder | None,
               old: dict | None = None) -> dict:
    point = {"id": card_id, "payload": payload, "vector": {}}
    if encoder is not None:
        point["payload"] = {**payload, "model_version": encoder.version}
        vectors = old.get("vector") if old else None
        if not vectors:
            vectors = encoder.encode(payload)
        if not vectors or set(vectors) != set(encoder.vector_config) or not all(vectors.values()):
            raise ValueError(f"Missing NI-25 vectors for {card_id}")
        point["vector"] = vectors
    return point


def prune_old_versions(db: httpx.Client, alias: str, previous: str | None):
    protected = {*aliases(db).values(), previous}
    version_name = re.compile(re.escape(alias) + r"__ni23_[a-f0-9]{32}")
    for row in request(db, "GET", "/collections")["collections"]:
        name = row["name"]
        if version_name.fullmatch(name) and name not in protected:
            request(db, "DELETE", f"/collections/{quote(name, safe='')}")


def sync_catalog(source: httpx.Client, db: httpx.Client, alias: str,
                 encoder: CardEncoder | None = None):
    active = aliases(db).get(alias)
    old_path = f"/collections/{quote(active, safe='')}" if active else None
    if old_path:
        metadata = request(db, "GET", old_path)["config"].get("metadata") or {}
    else:
        metadata = {}
        exists = request(db, "GET", f"/collections/{quote(alias, safe='')}/exists")
        if exists["exists"]:
            raise ValueError(f"{alias} is a physical collection; configure an unused catalog alias")

    version = encoder.version if encoder is not None else None
    old_version = metadata.get("model_version")
    if old_version is not None and encoder is None:
        raise ValueError("The active catalog has vectors; configure the NI-25 encoder before updating")

    bulk = source.get(SCRYFALL_BULK)
    bulk.raise_for_status()
    dump = next(row for row in bulk.json()["data"] if row["type"] == "oracle_cards")
    updated_at = dump["updated_at"]
    saved_at = metadata.get("scryfall_updated_at")
    if saved_at:
        current, saved = timestamp(updated_at), timestamp(saved_at)
        if current < saved or (current == saved and version == old_version):
            LOG.info("Catalog unchanged: new=0 changed=0, Scryfall version %s", saved_at)
            return
    else:
        timestamp(updated_at)

    pending = download_cards(source, dump)
    prune_old_versions(db, alias, previous=metadata.get("previous_collection"))
    staging = f"{alias}__ni23_{uuid4().hex}"
    stage_path = f"/collections/{quote(staging, safe='')}"
    request(db, "PUT", stage_path, json={
        "vectors": encoder.vector_config if encoder is not None else {},
        "on_disk_payload": True,
        "metadata": {
            "scryfall_updated_at": updated_at, "model_version": version,
            "previous_collection": active,
        },
    })
    request(db, "PUT", f"{stage_path}/index", params={"wait": "true"},
            json={"field_name": "name_keys", "field_schema": "keyword"})

    changed = 0
    retained = 0
    if old_path:
        for batch in old_batches(db, old_path, with_vectors=encoder is not None and old_version == version):
            points = []
            for old in batch:
                card_id = str(old["id"])
                old_payload = {key: value for key, value in old["payload"].items() if key != "model_version"}
                payload = pending.pop(card_id, None)
                if payload is None:
                    payload = old_payload
                    retained += 1
                differs = payload != old_payload
                changed += differs
                reuse = old if not differs and old_version == version else None
                points.append(make_point(card_id, payload, encoder, reuse))
            if points:
                request(db, "PUT", f"{stage_path}/points", params={"wait": "true"}, json={"points": points})

    added = len(pending)
    for batch in batched(pending.items(), BATCH_SIZE):
        points = [make_point(card_id, payload, encoder) for card_id, payload in batch]
        request(db, "PUT", f"{stage_path}/points", params={"wait": "true"}, json={"points": points})

    actions = []
    if active:
        actions.append({"delete_alias": {"alias_name": alias}})
    actions.append({"create_alias": {"collection_name": staging, "alias_name": alias}})
    request(db, "POST", "/collections/aliases", json={"actions": actions})
    LOG.info("Catalog updated: new=%d changed=%d retained=%d, Scryfall version %s",
             added, changed, retained, updated_at)
    try:
        prune_old_versions(db, alias, previous=active)
    except (httpx.HTTPError, ValueError, KeyError):
        LOG.exception("Could not clean up older catalog collections")


def run_once():
    import fcntl

    catalog = get_card_catalog()
    with open("/tmp/workshop-catalog-update.lock", "a") as lock:
        # The daily job and manual command share the updater container.
        fcntl.flock(lock, fcntl.LOCK_EX)
        with httpx.Client(headers=SCRYFALL_HEADERS, timeout=60, follow_redirects=True) as source:
            with httpx.Client(base_url=catalog.base_url, timeout=60, trust_env=False) as db:
                sync_catalog(source, db, catalog.collection)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily", action="store_true", help="Check on startup and every 24 hours")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    while True:
        started = time.monotonic()
        try:
            run_once()
        except Exception:
            LOG.exception("Catalog update failed")
            if not args.daily:
                return 1
        if not args.daily:
            return 0
        time.sleep(max(0, DAILY_SECONDS - (time.monotonic() - started)))


if __name__ == "__main__":
    raise SystemExit(main())
