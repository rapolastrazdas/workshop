from app.models import DeckCard
from test_decks import WHITE, RED, decks_data


def test_limit_rolls_back_and_maybeboard_stays_editable(decks_data):
    http, factory, headers, other_headers, ids, _ = decks_data
    with factory() as db:
        white = db.get(DeckCard, (ids[0], WHITE, "main"))
        white.quantity = 497
        db.commit()
    url = f"/api/decks/{ids[0]}/cards"
    add = {"oracle_id": WHITE, "list_name": "main", "action": "add"}
    assert http.post(url, headers=other_headers, json=add).status_code == 404
    assert http.post(url, headers=headers, json=add).status_code == 422
    response = http.post(url, headers=headers, json={**add, "oracle_id": RED, "list_name": "maybeboard"})
    assert response.status_code == 200
    assert response.json()["card_count"] == 500
    assert next(c for c in response.json()["cards"] if c["oracle_id"] == RED)["quantity"] == 100
    move = {"oracle_id": WHITE, "list_name": "maybeboard", "action": "move"}
    assert http.post(url, headers=headers, json=move).status_code == 422
    detail = http.get(f"/api/decks/{ids[0]}", headers=headers).json()
    assert detail["card_count"] == 500
    assert next(c for c in detail["cards"] if c["oracle_id"] == WHITE and c["list_name"] == "maybeboard")["quantity"] == 20
