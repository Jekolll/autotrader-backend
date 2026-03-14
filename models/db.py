# models/db.py
from sqlmodel import SQLModel, Field, create_engine, Session
from typing import Optional
from datetime import datetime
import os

engine = create_engine(
    os.getenv("DATABASE_URL", "sqlite:///./autotrader.db"),
    echo=False
)

class TradingSession(SQLModel, table=True):
    """Satu baris = satu user yang sedang/pernah login"""
    id:           Optional[int] = Field(default=None, primary_key=True)
    session_token: str          = Field(unique=True, index=True)
    mt5_login:    str
    mt5_password: str
    mt5_server:   str
    display_name: str           # "Login-12345678" sebagai label
    pairs:        str           = Field(default="")   # "EURUSD,GBPUSD"
    timeframe:    str           = Field(default="H1")
    risk_pct:     float         = Field(default=0.01)
    max_trades:   int           = Field(default=3)
    is_active:    bool          = Field(default=False)
    created_at:   datetime      = Field(default_factory=datetime.utcnow)


class TradeLog(SQLModel, table=True):
    id:           Optional[int]   = Field(default=None, primary_key=True)
    session_token: str            = Field(index=True)
    symbol:       str
    action:       str             # BUY / SELL
    lot:          float
    price:        float
    sl:           float
    tp:           float
    profit:       Optional[float] = None
    confidence:   float           = 0.0
    reason:       str             = ""
    ticket:       Optional[int]   = None
    opened_at:    datetime        = Field(default_factory=datetime.utcnow)
    closed_at:    Optional[datetime] = None


def create_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s
