from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ai import assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/ask")
async def ask(payload: dict[str, str]):
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")
    return {"text": await assistant.ask(text)}
