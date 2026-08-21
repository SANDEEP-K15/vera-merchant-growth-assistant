from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from vera.engine.compose import compose

BASE = Path(__file__).resolve().parents[2] / "../challenge/expanded"


def load_dir(dirname: str, key: str) -> dict[str, dict]:
    out = {}
    for path in (BASE / dirname).glob("*.json"):
        data = json.loads(path.read_text())
        out[data[key]] = data
    return out


def load_data():
    categories = load_dir("categories", "slug")
    merchants = load_dir("merchants", "merchant_id")
    customers = load_dir("customers", "customer_id")
    triggers = load_dir("triggers", "id")
    pairs = json.loads((BASE / "test_pairs.json").read_text())["pairs"]
    return categories, merchants, customers, triggers, pairs


def numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<!\w)\d+(?:\.\d+)?%?|₹\s?\d[\d,]*", text))


def score_message(category: dict, merchant: dict, trigger: dict, customer: dict | None, result: dict) -> dict[str, Any]:
    body = result["body"]
    lower = body.lower()
    p = trigger.get("payload") or {}
    identity = merchant.get("identity") or {}
    perf = merchant.get("performance") or {}

    score = {"specificity": 0, "category_fit": 0, "merchant_fit": 0,
             "trigger_relevance": 0, "engagement": 0, "penalties": 0, "reasons": []}

    # Specificity: concrete facts from trigger / merchant.
    facts = []
    for value in p.values():
        if isinstance(value, (str, int, float)):
            facts.append(str(value).lower())
    for value in [identity.get("name"), identity.get("city"), identity.get("locality")]:
        if value:
            facts.append(str(value).lower())
    if any(x in lower for x in facts if len(x) >= 3):
        score["specificity"] += 5
    if numbers(body):
        score["specificity"] += 2
    if p and any(str(v).lower() in lower for v in p.values() if isinstance(v, str) and len(v) >= 5):
        score["specificity"] += 2
    if len(body) <= 420:
        score["specificity"] += 1

    # Category fit: basic category-specific vocabulary / voice.
    slug = category.get("slug", "")
    category_terms = {
        "dentists": ["dental", "cleaning", "patient", "clinical", "x-ray", "caries", "fluoride"],
        "salons": ["salon", "hair", "stylist", "beauty", "appointment", "service"],
        "restaurants": ["restaurant", "thali", "lunch", "dinner", "covers", "offer"],
        "gyms": ["gym", "training", "yoga", "workout", "session", "members"],
        "pharmacies": ["pharmacy", "refill", "medicine", "molecule", "stock", "delivery"],
    }
    if any(term in lower for term in category_terms.get(slug, [])):
        score["category_fit"] += 7
    else:
        score["category_fit"] += 4
    taboos = [str(x).lower() for x in (category.get("voice") or {}).get("vocab_taboo", [])]
    if any(t and t in lower for t in taboos):
        score["penalties"] += 3
        score["reasons"].append("taboo vocabulary")

    # Merchant fit.
    if identity.get("name", "").lower() in lower or identity.get("owner_first_name", "").lower() in lower:
        score["merchant_fit"] += 3
    merchant_values = [str(perf.get(k)) for k in ("views", "calls", "directions", "ctr") if perf.get(k) is not None]
    if any(v in body for v in merchant_values):
        score["merchant_fit"] += 3
    if merchant.get("offers") and any(o.get("title", "").lower() in lower for o in merchant["offers"] if o.get("status") == "active"):
        score["merchant_fit"] += 2
    if customer and customer.get("identity", {}).get("name", "").lower() in lower:
        score["merchant_fit"] += 2
    score["merchant_fit"] = min(score["merchant_fit"], 10)

    # Trigger relevance: trigger kind words or payload facts.
    kind_words = trigger.get("kind", "").replace("_", " ").lower().split()
    matched = sum(1 for w in kind_words if len(w) >= 4 and w in lower)
    payload_hits = sum(1 for v in p.values() if isinstance(v, str) and len(v) >= 5 and v.lower() in lower)
    score["trigger_relevance"] = min(10, 4 + matched + min(4, payload_hits))

    # Engagement: one CTA, actionable/curiosity language.
    cta = result.get("cta")
    if cta in {"binary_yes_no", "binary_confirm_cancel", "multi_choice_slot", "open_ended"}:
        score["engagement"] += 6
    if re.search(r"\b(want me|should i|shall i|reply yes|can i|need me)\b", lower):
        score["engagement"] += 3
    if body.rstrip().endswith("?"):
        score["engagement"] += 1
    score["engagement"] = min(score["engagement"], 10)

    score["specificity"] = min(score["specificity"], 10)
    score["category_fit"] = min(score["category_fit"], 10)
    score["trigger_relevance"] = min(score["trigger_relevance"], 10)
    score["total"] = sum(score[k] for k in ("specificity", "category_fit", "merchant_fit", "trigger_relevance", "engagement")) - score["penalties"]
    return score


def run():
    categories, merchants, customers, triggers, pairs = load_data()
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pairs", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    selected = []
    if args.all:
        selected = [{"test_id": tid, "trigger_id": tid, "merchant_id": t.get("merchant_id"), "customer_id": t.get("customer_id")} for tid, t in triggers.items()]
    else:
        selected = pairs

    totals = {k: 0 for k in ("specificity", "category_fit", "merchant_fit", "trigger_relevance", "engagement", "total")}
    weak = []

    for pair in selected:
        trigger = triggers[pair["trigger_id"]]
        merchant = merchants[pair["merchant_id"]]
        category = categories[merchant["category_slug"]]
        customer = customers.get(pair.get("customer_id")) if pair.get("customer_id") else None
        result = compose(category, merchant, trigger, customer)
        s = score_message(category, merchant, trigger, customer, result)
        for k in totals:
            totals[k] += s[k]
        if s["total"] < 32:
            weak.append((pair.get("test_id", pair["trigger_id"]), trigger["kind"], s["total"], result["body"]))
        if args.show:
            print(f"{pair.get('test_id', pair['trigger_id'])} | {trigger['kind']} | {s['total']}/50 | {result['body']}")

    n = len(selected)
    print(f"Evaluated: {n}")
    print(f"Average: {totals['total']/n:.1f}/50")
    for k in ("specificity", "category_fit", "merchant_fit", "trigger_relevance", "engagement"):
        print(f"{k:20}: {totals[k]/n:.1f}/10")
    print(f"weak_cases           : {len(weak)}")
    for row in weak[:20]:
        print("WEAK", row)


if __name__ == "__main__":
    run()
