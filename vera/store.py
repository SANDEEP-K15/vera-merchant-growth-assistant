from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

@dataclass
class StoredContext:
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: datetime
    stored_at: datetime

@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    turns: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    auto_reply_detected: bool = False
    action_mode: bool = False
    last_trigger_id: Optional[str] = None
    last_suppression_key: Optional[str] = None
    last_sent_at: Optional[datetime] = None

class VeraStore:
    def __init__(self) -> None:
        self.contexts: dict[tuple[str, str], StoredContext] = {}
        self.conversations: dict[str, ConversationState] = {}
        self.sent_suppressions: dict[str, float] = {}
        self.lock = asyncio.Lock()
        self.started = time.monotonic()

    async def put_context(self, env) -> tuple[bool, int | None, StoredContext]:
        key = (env.scope, env.context_id)
        async with self.lock:
            current = self.contexts.get(key)
            if current is not None and env.version <= current.version:
                return False, current.version, current
            now = datetime.now(env.delivered_at.tzinfo)
            stored = StoredContext(env.scope, env.context_id, env.version, env.payload, env.delivered_at, now)
            self.contexts[key] = stored
            return True, None, stored

    async def get(self, scope: str, context_id: str) -> StoredContext | None:
        async with self.lock:
            return self.contexts.get((scope, context_id))

    async def counts(self) -> dict[str, int]:
        async with self.lock:
            out = {x: 0 for x in ('category', 'merchant', 'customer', 'trigger')}
            for c in self.contexts.values():
                if c.scope in out:
                    out[c.scope] += 1
            return out

    def uptime(self) -> float:
        return time.monotonic() - self.started

    async def get_or_create_conversation(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: str | None = None,
    ) -> ConversationState:
        async with self.lock:
            state = self.conversations.get(conversation_id)
            if state is None:
                state = ConversationState(conversation_id, merchant_id, customer_id)
                self.conversations[conversation_id] = state
            return state

    async def get_conversation(self, conversation_id: str) -> ConversationState | None:
        async with self.lock:
            return self.conversations.get(conversation_id)

    async def mutate_conversation(self, conversation_id: str, **updates: Any) -> ConversationState | None:
        async with self.lock:
            state = self.conversations.get(conversation_id)
            if state is None:
                return None
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            return state

    async def append_turn(self, conversation_id: str, turn: dict[str, Any]) -> ConversationState | None:
        async with self.lock:
            state = self.conversations.get(conversation_id)
            if state is None:
                return None
            state.turns.append(turn)
            return state

    async def claim_suppression(self, suppression_key: str) -> bool:
        """Atomically check-and-claim a suppression key.

        Returns True only for the request that successfully claims it.
        This prevents duplicate sends when two /tick calls race.
        """
        async with self.lock:
            if suppression_key in self.sent_suppressions:
                return False
            self.sent_suppressions[suppression_key] = time.time()
            return True

    async def mark_sent(self, suppression_key: str) -> None:
        async with self.lock:
            self.sent_suppressions[suppression_key] = time.time()

    async def already_sent(self, suppression_key: str) -> bool:
        async with self.lock:
            return suppression_key in self.sent_suppressions
