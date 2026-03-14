# routers/trades.py
from fastapi import APIRouter, Header
from sqlmodel import Session, select
from models.db import TradeLog, engine

router = APIRouter()

def _token(authorization: str = Header(...)) -> str:
    return authorization.replace("Bearer ", "")

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
