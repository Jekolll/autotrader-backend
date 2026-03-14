# routers/bot.py
from fastapi import APIRouter, Header
from sqlmodel import Session, select
from models.db import TradingSession, engine

router = APIRouter()

def _token(authorization: str = Header(...)) -> str:
    return authorization.replace("Bearer ", "")

@router.post("/start")
def start(authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
        if row:
            row.is_active = True
            s.add(row); s.commit()
    return {"ok": True, "msg": "Bot aktif"}

@router.post("/stop")
def stop(authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
        if row:
            row.is_active = False
            s.add(row); s.commit()
    return {"ok": True, "msg": "Bot dihentikan"}

@router.get("/status")
def get_status(authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
    if not row:
        return {"status": "stopped", "last_run": None, "error": None}
    return {
        "status":   "running" if row.is_active else "stopped",
        "last_run": row.updated_at.isoformat() if row.updated_at else None,
        "error":    None,
    }
