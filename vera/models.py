from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

class VeraModel(BaseModel):
    model_config = ConfigDict(extra='allow')

class ContextEnvelope(VeraModel):
    scope: Literal['category','merchant','customer','trigger']
    context_id: str
    version: int = Field(ge=1)
    payload: dict[str, Any]
    delivered_at: datetime

class TickRequest(VeraModel):
    now: datetime
    available_triggers: list[str] = Field(default_factory=list)

class ReplyRequest(VeraModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: Literal['merchant','customer'] = 'merchant'
    message: str
    received_at: datetime
    turn_number: int = Field(ge=1)

class ComposedMessage(VeraModel):
    body: str = Field(min_length=1)
    cta: Literal['binary_yes_no','binary_confirm_cancel','multi_choice_slot','open_ended','none']
    send_as: Literal['vera','merchant_on_behalf']
    suppression_key: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

class TickAction(VeraModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Literal['vera','merchant_on_behalf']
    trigger_id: str
    template_name: str
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: Literal['binary_yes_no','binary_confirm_cancel','multi_choice_slot','open_ended','none']
    suppression_key: str
    rationale: str

class TickResponse(VeraModel):
    actions: list[TickAction] = Field(default_factory=list)
