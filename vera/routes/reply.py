from fastapi import APIRouter, Request

from ..engine.deterministic import classify_intent, is_auto_reply
from ..models import ReplyRequest

router = APIRouter(prefix="/v1")


@router.post("/reply")
async def reply(body: ReplyRequest, request: Request):
    store = request.app.state.store
    state = await store.get_or_create_conversation(
        body.conversation_id,
        body.merchant_id,
        body.customer_id,
    )

    msg = body.message.strip()

    # A conversation that has already ended must never be reactivated by a
    # later positive message. This is especially important after opt-out.
    if not state.active:
        return {
            "action": "end",
            "rationale": "Conversation is already inactive; no later reply can reactivate it.",
        }

    # Explicit opt-out / hostility wins over every other interpretation.
    intent = classify_intent(msg)
    if intent == "negative":
        state.active = False
        state.turns.append({"from": body.from_role, "body": msg})
        return {
            "action": "end",
            "rationale": "Explicit opt-out or negative intent detected; conversation is stopped.",
        }

    if is_auto_reply(msg, state.turns):
        state.auto_reply_detected = True
        state.active = False
        state.turns.append({"from": body.from_role, "body": msg})
        return {
            "action": "end",
            "rationale": "WhatsApp Business auto-reply pattern detected; stopping instead of burning additional turns.",
        }

    state.turns.append({
        "from": body.from_role,
        "body": msg,
        "received_at": body.received_at.isoformat(),
    })

    if intent == "positive":
        state.action_mode = True
        return {
            "action": "send",
            "body": "Got it — proceeding to the next step now. I’ll use the context already available rather than asking you to repeat the details.",
            "cta": "none",
            "rationale": "Explicit positive intent detected; route directly to execution instead of re-qualifying.",
        }

    if not state.active:
        return {"action": "end", "rationale": "Conversation is inactive."}

    return {
        "action": "wait",
        "wait_seconds": 0,
        "rationale": "No sufficiently clear action intent was detected; preserve context and avoid unnecessary messaging.",
    }
