# routers/trades.py
from fastapi import APIRouter, Header
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, select
from typing import Optional
from datetime import datetime
from models.db import TradeLog, engine

router = APIRouter()

def _token(authorization: str = Header(...)) -> str:
    return authorization.replace("Bearer ", "")


# ── Riwayat & Summary ─────────────────────────────────────────

@router.get("/history")
def history(limit: int = 100, authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        logs = s.exec(
            select(TradeLog)
            .where(TradeLog.session_token == token)
            .order_by(TradeLog.opened_at.desc())
            .limit(limit)
        ).all()
    return [
        {
            "id":         t.id,
            "symbol":     t.symbol,
            "action":     t.action,
            "lot":        t.lot,
            "price":      t.price,
            "sl":         t.sl,
            "tp":         t.tp,
            "profit":     t.profit,
            "confidence": t.confidence,
            "reason":     t.reason,
            "opened_at":  t.opened_at.isoformat(),
        }
        for t in logs
    ]

@router.get("/summary")
def summary(authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        logs = s.exec(select(TradeLog).where(TradeLog.session_token == token)).all()
    profits = [t.profit for t in logs if t.profit is not None]
    wins    = sum(1 for p in profits if p > 0)
    return {
        "total":      len(logs),
        "profit":     round(sum(profits), 2),
        "win_rate":   round(wins / len(profits) * 100, 1) if profits else 0.0,
        "avg_profit": round(sum(profits) / len(profits), 2) if profits else 0.0,
    }


# ── Log trade dari local bot ──────────────────────────────────

class TradeLogBody(BaseModel):
    symbol:     str
    action:     str
    lot:        float
    price:      float
    sl:         float
    tp:         float
    confidence: float = 0.0
    reason:     str   = ""

@router.post("/log")
def log_trade(body: TradeLogBody, authorization: str = Header(...)):
    token = _token(authorization)
    with Session(engine) as s:
        s.add(TradeLog(
            session_token = token,
            symbol        = body.symbol,
            action        = body.action,
            lot           = body.lot,
            price         = body.price,
            sl            = body.sl,
            tp            = body.tp,
            confidence    = body.confidence,
            reason        = body.reason,
        ))
        s.commit()
    return {"ok": True}


# ── Live posisi dari local bot ────────────────────────────────

class PositionBody(BaseModel):
    positions: list[dict]

@router.post("/positions")
def update_positions(body: PositionBody, authorization: str = Header(...)):
    """Local bot kirim data posisi terbuka setiap loop"""
    token = _token(authorization)
    # Simpan di cache memory (cukup untuk live display)
    positions_cache[token] = {
        "data":       body.positions,
        "updated_at": datetime.utcnow().isoformat(),
    }
    return {"ok": True}

@router.get("/positions")
def get_positions(authorization: str = Header(...)):
    token = _token(authorization)
    cached = positions_cache.get(token)
    if not cached:
        return {"positions": [], "updated_at": None}
    return {"positions": cached["data"], "updated_at": cached["updated_at"]}

# Cache in-memory untuk posisi live
positions_cache: dict = {}
