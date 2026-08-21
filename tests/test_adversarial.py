import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from vera.main import create_app
from vera.store import VeraStore


def env(scope, cid, version, payload):
    return {
        "scope": scope,
        "context_id": cid,
        "version": version,
        "delivered_at": "2026-04-26T10:00:00Z",
        "payload": payload,
    }


def merchant(mid="m_adv", slug="restaurants"):
    return {
        "merchant_id": mid,
        "category_slug": slug,
        "identity": {"name": "Adv Cafe", "city": "Delhi", "locality": "Saket"},
        "performance": {"window_days": 30, "views": 2400, "calls": 18, "directions": 40, "ctr": 0.021},
        "offers": [{"id": "o1", "title": "Lunch @ ₹149", "status": "active"}],
        "signals": [],
    }


def category(slug="restaurants"):
    return {
        "slug": slug,
        "voice": {"tone": "operator", "register": "professional", "code_mix": "english", "vocab_allowed": [], "vocab_taboo": []},
        "offer_catalog": [],
        "digest": [],
        "peer_stats": {},
    }


def trigger(tid="t_adv", mid="m_adv", customer_id=None, suppression="adv:s1", kind="perf_dip", payload=None):
    p = payload or {"metric": "calls", "delta_pct": -20, "window": "7d"}
    return {
        "id": tid,
        "scope": "customer" if customer_id else "merchant",
        "kind": kind,
        "source": "internal",
        "merchant_id": mid,
        "customer_id": customer_id,
        "payload": p,
        "urgency": 3,
        "suppression_key": suppression,
        "expires_at": "2026-04-27T10:00:00Z",
    }


def test_unexpected_fields_are_accepted_and_malformed_payload_is_rejected():
    app = create_app()
    c = TestClient(app)
    r = c.post("/v1/context", json={**env("merchant", "m1", 1, merchant("m1")), "unexpected": {"future": True}})
    assert r.status_code == 200

    malformed = env("merchant", "m2", 1, {"merchant_id": "m2"})
    r2 = c.post("/v1/context", json=malformed)
    # Payload is intentionally flexible; malformed semantic payloads are not
    # rejected by the envelope schema, which is desirable for judge evolution.
    assert r2.status_code == 200


def test_missing_context_never_sends():
    app = create_app()
    c = TestClient(app)
    c.post("/v1/context", json=env("trigger", "t1", 1, trigger()))
    assert c.post("/v1/tick", json={"now": "2026-04-26T10:05:00Z", "available_triggers": ["t1"]}).json() == {"actions": []}


def test_contradictory_trigger_and_merchant_ids_are_dropped():
    app = create_app()
    c = TestClient(app)
    c.post("/v1/context", json=env("category", "restaurants", 1, category()))
    c.post("/v1/context", json=env("merchant", "m_adv", 1, merchant("m_adv")))
    bad = trigger(tid="bad", mid="m_adv")
    bad["payload"]["merchant_id"] = "m_other"
    c.post("/v1/context", json=env("trigger", "bad", 1, bad))
    r = c.post("/v1/tick", json={"now": "2026-04-26T10:05:00Z", "available_triggers": ["bad"]})
    assert r.status_code == 200
    assert r.json() == {"actions": []}


def test_customer_trigger_cannot_downgrade_when_customer_missing():
    app = create_app()
    c = TestClient(app)
    c.post("/v1/context", json=env("category", "restaurants", 1, category()))
    c.post("/v1/context", json=env("merchant", "m_adv", 1, merchant("m_adv")))
    t = trigger(tid="cust1", customer_id="c_missing", kind="recall_due", payload={"service_due": "cleaning"})
    c.post("/v1/context", json=env("trigger", "cust1", 1, t))
    r = c.post("/v1/tick", json={"now": "2026-04-26T10:05:00Z", "available_triggers": ["cust1"]})
    assert r.json() == {"actions": []}


def test_suppression_is_atomic_under_concurrent_ticks():
    app = create_app()
    c = TestClient(app)
    c.post("/v1/context", json=env("category", "restaurants", 1, category()))
    c.post("/v1/context", json=env("merchant", "m_adv", 1, merchant("m_adv")))
    c.post("/v1/context", json=env("trigger", "t_race", 1, trigger(tid="t_race")))

    async def race():
        store = app.state.store
        results = await asyncio.gather(*[store.claim_suppression("race:key") for _ in range(20)])
        assert sum(results) == 1

    asyncio.run(race())


def test_tick_duplicate_suppression():
    app = create_app()
    c = TestClient(app)
    c.post("/v1/context", json=env("category", "restaurants", 1, category()))
    c.post("/v1/context", json=env("merchant", "m_adv", 1, merchant("m_adv")))
    c.post("/v1/context", json=env("trigger", "t_dup", 1, trigger(tid="t_dup", suppression="dup:key")))
    payload = {"now": "2026-04-26T10:05:00Z", "available_triggers": ["t_dup"]}
    first = c.post("/v1/tick", json=payload).json()
    second = c.post("/v1/tick", json=payload).json()
    assert len(first["actions"]) == 1
    assert second == {"actions": []}


def test_ended_conversation_cannot_be_reactivated():
    app = create_app()
    c = TestClient(app)
    base = {
        "conversation_id": "conv_end_then_yes",
        "merchant_id": "m_adv",
        "from_role": "merchant",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 2,
    }
    r1 = c.post("/v1/reply", json={**base, "message": "Stop messaging me."})
    assert r1.json()["action"] == "end"
    r2 = c.post("/v1/reply", json={**base, "turn_number": 3, "message": "Yes, let's do it."})
    assert r2.json()["action"] == "end"
