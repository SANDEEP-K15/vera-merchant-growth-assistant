from fastapi.testclient import TestClient

from vera.main import app

client = TestClient(app)


def envelope(scope="merchant", context_id="m_test", version=1, payload=None):
    return {
        "scope": scope,
        "context_id": context_id,
        "version": version,
        "delivered_at": "2026-04-26T10:00:00Z",
        "payload": payload or {
            "merchant_id": "m_test",
            "category_slug": "restaurants",
            "identity": {"name": "Test Cafe", "city": "Delhi", "locality": "Saket"},
        },
    }


def test_healthz():
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_context_versioning():
    r1 = client.post("/v1/context", json=envelope(version=1))
    assert r1.status_code == 200

    same = client.post("/v1/context", json=envelope(version=1))
    assert same.status_code == 409
    assert same.json()["detail"]["reason"] == "stale_version"

    lower = client.post("/v1/context", json=envelope(version=0))
    assert lower.status_code == 400

    higher = client.post("/v1/context", json=envelope(version=2))
    assert higher.status_code == 200


def test_invalid_scope_is_400():
    r = client.post("/v1/context", json=envelope(scope="bad"))
    assert r.status_code == 400
    assert r.json()["detail"]["reason"] == "invalid_scope"


def test_reply_intent_and_hostility():
    positive = client.post("/v1/reply", json={
        "conversation_id": "conv_test_positive",
        "merchant_id": "m_test",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 2,
    })
    assert positive.status_code == 200
    assert positive.json()["action"] == "send"
    assert "next" in positive.json()["body"].lower() or "proceed" in positive.json()["body"].lower()

    hostile = client.post("/v1/reply", json={
        "conversation_id": "conv_test_hostile",
        "merchant_id": "m_test",
        "from_role": "merchant",
        "message": "Stop messaging me. This is useless spam.",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 2,
    })
    assert hostile.status_code == 200
    assert hostile.json()["action"] == "end"


def test_auto_reply_ends():
    r = client.post("/v1/reply", json={
        "conversation_id": "conv_test_auto",
        "merchant_id": "m_test",
        "from_role": "merchant",
        "message": "Thank you for contacting us! Our team will respond shortly.",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 2,
    })
    assert r.status_code == 200
    assert r.json()["action"] == "end"
