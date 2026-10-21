"""Server-side chat history — always scoped to the authenticated user."""
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.security_deps import require_user
from app.auth.models import UserRecord
from app.conversations.store import (
    ConversationRecord,
    encode_messages,
    get_conversation_store,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str
    mode: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ConversationUpsert(BaseModel):
    id: str | None = None
    title: str = "New chat"
    mode: str = "chat"
    messages: list[dict[str, Any]] = Field(default_factory=list)


def _out(rec: ConversationRecord) -> ConversationOut:
    try:
        messages = json.loads(rec.messages_json or "[]")
    except json.JSONDecodeError:
        messages = []
    return ConversationOut(
        id=rec.id,
        title=rec.title,
        mode=rec.mode,
        messages=messages if isinstance(messages, list) else [],
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: Annotated[UserRecord, Depends(require_user)],
    limit: int = 50,
) -> list[ConversationOut]:
    store = get_conversation_store()
    return [_out(r) for r in store.list_for_user(user.id, limit=min(max(limit, 1), 200))]


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    user: Annotated[UserRecord, Depends(require_user)],
) -> ConversationOut:
    rec = get_conversation_store().get(conversation_id, user.id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _out(rec)


@router.put("", response_model=ConversationOut)
async def upsert_conversation(
    body: ConversationUpsert,
    user: Annotated[UserRecord, Depends(require_user)],
) -> ConversationOut:
    store = get_conversation_store()
    if body.id:
        existing = store.get(body.id, user.id)
        if existing is None:
            # Either missing or owned by another user — never allow takeover.
            raise HTTPException(status_code=404, detail="Conversation not found")
        rec = ConversationRecord(
            id=existing.id,
            user_id=user.id,
            title=body.title,
            mode=body.mode,
            messages_json=encode_messages(body.messages),
            created_at=existing.created_at,
        )
    else:
        rec = ConversationRecord(
            id=uuid4().hex,
            user_id=user.id,
            title=body.title,
            mode=body.mode,
            messages_json=encode_messages(body.messages),
        )
    saved = store.upsert(rec)
    check = store.get(saved.id, user.id)
    if check is None:
        raise HTTPException(status_code=403, detail="Access denied")
    return _out(check)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict:
    deleted = get_conversation_store().delete(conversation_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "id": conversation_id}
