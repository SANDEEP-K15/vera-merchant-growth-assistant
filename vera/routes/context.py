from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from ..models import ContextEnvelope

router = APIRouter(prefix="/v1")


@router.post("/context")
async def context(body: dict, request: Request):
    """Push versioned context with explicit 400/409 challenge semantics."""
    try:
        envelope = ContextEnvelope.model_validate(body)
    except ValidationError as exc:
        scope = body.get("scope") if isinstance(body, dict) else None
        reason = "invalid_scope" if scope not in {"category", "merchant", "customer", "trigger"} else "malformed_context"
        raise HTTPException(
            status_code=400,
            detail={
                "accepted": False,
                "reason": reason,
                "details": exc.errors(),
            },
        )

    ok, current, stored = await request.app.state.store.put_context(envelope)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail={
                "accepted": False,
                "reason": "stale_version",
                "current_version": current,
            },
        )

    return {
        "accepted": True,
        "ack_id": f"ack_{envelope.context_id}_v{envelope.version}",
        "stored_at": stored.stored_at,
    }
