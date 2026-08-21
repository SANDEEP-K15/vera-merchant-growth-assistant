from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ..engine.compose import compose
from ..engine.deterministic import score_trigger
from ..models import TickRequest, TickAction

router = APIRouter(prefix="/v1")


def template_for(first_outbound: bool) -> tuple[str, list[str]]:
    return ("vera_contextual_v1", []) if first_outbound else ("freeform", [])


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.post("/tick")
async def tick(body: TickRequest, request: Request):
    store = request.app.state.store
    now = _as_aware(body.now)
    candidates = []

    for trigger_id in body.available_triggers:
        tc = await store.get("trigger", trigger_id)
        if not tc:
            continue

        trigger = tc.payload
        expires_raw = trigger.get("expires_at")
        if expires_raw:
            try:
                expires = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
                if _as_aware(expires) <= now:
                    continue
            except ValueError:
                # Invalid expiry is unsafe for an outbound message.
                continue

        merchant_id = trigger.get("merchant_id") or (trigger.get("payload") or {}).get("merchant_id")
        if not merchant_id:
            continue

        mc = await store.get("merchant", merchant_id)
        if not mc:
            continue

        merchant = mc.payload

        # The trigger and merchant context must agree. A contradictory payload
        # is unsafe to act on; do not silently choose one side.
        if merchant.get("merchant_id") and merchant.get("merchant_id") != merchant_id:
            continue

        category = await store.get("category", merchant.get("category_slug", ""))
        if not category:
            continue

        customer_id = trigger.get("customer_id") or (trigger.get("payload") or {}).get("customer_id")
        customer = None
        if customer_id:
            customer_ctx = await store.get("customer", customer_id)
            # Never downgrade a customer trigger into a merchant message.
            if not customer_ctx:
                continue
            customer = customer_ctx.payload
            if customer.get("customer_id") and customer.get("customer_id") != customer_id:
                continue
            if customer.get("merchant_id") and customer.get("merchant_id") != merchant_id:
                continue

        # If the trigger payload redundantly contains merchant/customer IDs,
        # reject contradictions rather than composing against the wrong party.
        tp = trigger.get("payload") or {}
        if tp.get("merchant_id") and tp.get("merchant_id") != merchant_id:
            continue
        if tp.get("customer_id") and customer_id and tp.get("customer_id") != customer_id:
            continue

        candidates.append((trigger, merchant, category.payload, customer))

    if not candidates:
        return {"actions": []}

    # At most one outbound per merchant/customer relationship per tick.
    grouped: dict[tuple[str, str | None], list[tuple]] = {}
    for candidate in candidates:
        trigger, merchant, category, customer = candidate
        key = (merchant.get("merchant_id"), customer.get("customer_id") if customer else None)
        grouped.setdefault(key, []).append(candidate)

    actions: list[TickAction] = []

    for _, items in grouped.items():
        trigger, merchant, category, customer = max(
            items,
            key=lambda x: score_trigger(x[0], x[1], x[2], x[3]),
        )

        suppression = trigger.get("suppression_key") or f"{trigger.get('kind')}:{trigger.get('id')}"

        # Compose before claiming. If composition fails, a later tick can
        # safely retry. The final claim immediately before append/send remains
        # atomic, so concurrent ticks still cannot emit duplicates.
        decision = compose(category, merchant, trigger, customer)
        if not await store.claim_suppression(suppression):
            continue

        conversation_id = f"conv_{trigger.get('id')}"
        state = await store.get_or_create_conversation(
            conversation_id,
            merchant.get("merchant_id"),
            customer.get("customer_id") if customer else None,
        )

        template_name, template_params = template_for(len(state.turns) == 0)
        action = TickAction(
            conversation_id=conversation_id,
            merchant_id=merchant.get("merchant_id"),
            customer_id=customer.get("customer_id") if customer else None,
            send_as=decision["send_as"],
            trigger_id=trigger.get("id"),
            template_name=template_name,
            template_params=template_params,
            body=decision["body"],
            cta=decision["cta"],
            suppression_key=decision["suppression_key"],
            rationale=decision["rationale"],
        )
        actions.append(action)

        await store.mutate_conversation(
            conversation_id,
            last_trigger_id=trigger.get("id"),
            last_suppression_key=suppression,
            last_sent_at=now,
        )
        await store.append_turn(conversation_id, {
            "from": "vera",
            "body": decision["body"],
            "trigger_id": trigger.get("id"),
            "received_at": now.isoformat(),
        })

    return {"actions": [a.model_dump() for a in actions]}
