"""Load missing public card metadata for local deck import and display."""

import gzip
import json
from tempfile import TemporaryFile
from urllib.parse import quote

import httpx

from .card_catalog import CardCatalog
from .card_import import card_name_keys


def card_point(card):
    faces = card.get("card_faces", [])
    front = faces[0] if faces else {}
    return {
        "id": card["oracle_id"],
        "vector": {},
        "payload": {
            "name": card["name"],
            "name_keys": card_name_keys(card["name"]),
            "mana_cost": card.get("mana_cost", front.get("mana_cost", "")),
            "cmc": card.get("cmc", front.get("cmc")),
            "colors": card.get("colors", front.get("colors", [])),
            "type_line": card.get("type_line", front.get("type_line", "")),
        },
    }


def main():
    catalog = CardCatalog()
    collection = "/collections/" + quote(catalog.collection, safe="")
    headers = {"Accept": "application/json", "User-Agent": "UrzasWorkshop/1.0"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=90) as source, TemporaryFile() as archive:
        descriptor = source.get("https://api.scryfall.com/bulk-data/oracle-cards").raise_for_status().json()
        with source.stream("GET", descriptor["jsonl_download_uri"]) as download:
            download.raise_for_status()
            for chunk in download.iter_raw():
                archive.write(chunk)
        archive.seek(0)

        with httpx.Client(base_url=catalog.base_url, timeout=60) as database, gzip.open(archive, "rt", encoding="utf8") as cards:
            status = database.get(collection)
            if status.status_code == 404:
                database.put(collection, json={"vectors": {}}).raise_for_status()
            else:
                status.raise_for_status()
            batch = []
            processed = 0
            for line in cards:
                card = json.loads(line)
                if not card.get("oracle_id"):
                    continue
                batch.append(card_point(card))
                if len(batch) == 500:
                    insert_missing(database, collection, batch)
                    processed += len(batch)
                    batch.clear()
            if batch:
                insert_missing(database, collection, batch)
            print(f"Patikrinta kortų: {processed + len(batch)}")


def insert_missing(database, collection, points):
    # Preserve any existing metadata and model vectors, including on a retry.
    endpoint = collection + "/points"
    existing = database.post(endpoint, json={
        "ids": [point["id"] for point in points], "with_payload": False, "with_vector": False,
    }).raise_for_status().json()["result"]
    known_ids = {point["id"] for point in existing}
    missing = [point for point in points if point["id"] not in known_ids]
    if missing:
        database.put(endpoint, params={"wait": "true"}, json={"points": missing}).raise_for_status()


if __name__ == "__main__":
    main()
