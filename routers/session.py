# routers/session.py
import secrets
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from models.db import TradingSession, engine, get_session
from services.mt5_connector import MT5Connector

router = APIRouter()

FOREX_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD",
    "USDCAD","NZDUSD","EURGBP","EURJPY","GBPJPY",
    "XAUUSD","XAGUSD","US30","NAS100","SP500",
]


class LoginBody(BaseModel):
    mt5_login:    str
    mt5_password: str
    mt5_server:   str


def _get_session(authorization: str = Header(...)) -> TradingSession:
    token = authorization.replace("Bearer ", "")
    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
    if not row:
        raise HTTPException(401, "Session tidak valid atau sudah expired")
    return row


@router.post("/login")
def login(body: LoginBody):
    """Coba konek ke MT5 — kalau berhasil, buat session token"""
    conn = MT5Connector(int(body.mt5_login), body.mt5_password, body.mt5_server)
    ok, msg = conn.connect()
    conn.disconnect()
    
    # Parse info dari msg "OK|balance|currency|server"
    parts   = msg.split("|")
    balance = parts[1] if len(parts) > 1 else "?"
    currency = parts[2] if len(parts) > 2 else "USD"

    token = secrets.token_urlsafe(32)

    with Session(engine) as s:
        # Kalau sudah pernah login dengan akun ini, update token-nya
        existing = s.exec(
            select(TradingSession).where(TradingSession.mt5_login == body.mt5_login)
        ).first()

        if existing:
            existing.session_token = token
            existing.mt5_password  = body.mt5_password
            existing.mt5_server    = body.mt5_server
            s.add(existing)
        else:
            s.add(TradingSession(
                session_token = token,
                mt5_login     = body.mt5_login,
                mt5_password  = body.mt5_password,
                mt5_server    = body.mt5_server,
                display_name  = f"Akun {body.mt5_login}",
            ))
        s.commit()

    return {
        "token":    token,
        "login":    body.mt5_login,
        "balance":  balance,
        "currency": currency,
        "pairs":    FOREX_PAIRS,
    }


@router.get("/me")
def me(row: TradingSession = Depends(_get_session)):
    return {
        "login":       row.mt5_login,
        "display":     row.display_name,
        "pairs":       [p for p in row.pairs.split(",") if p],
        "timeframe":   row.timeframe,
        "risk_pct":    row.risk_pct,
        "max_trades":  row.max_trades,
        "is_active":   row.is_active,
    }


class PairsBody(BaseModel):
    pairs:      list[str]
    timeframe:  str   = "H1"
    risk_pct:   float = 0.01
    max_trades: int   = 3


@router.post("/settings")
def save_settings(body: PairsBody, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
        if not row: raise HTTPException(401, "Session tidak valid")
        row.pairs      = ",".join(body.pairs)
        row.timeframe  = body.timeframe
        row.risk_pct   = body.risk_pct
        row.max_trades = body.max_trades
        s.add(row); s.commit()
    return {"ok": True}
