# services/bot_runner.py
# Satu thread per session — isolated, tidak saling ganggu

import threading, time
from datetime import datetime
from sqlmodel import Session, select
from models.db import TradingSession, TradeLog, engine
from services.mt5_connector import MT5Connector
from services.algorithms import combine

_bots: dict[str, "BotThread"] = {}


class BotThread(threading.Thread):
    def __init__(self, token: str, cfg: TradingSession):
        super().__init__(daemon=True)
        self.token   = token
        self.cfg     = cfg
        self._stop   = threading.Event()
        self.status  = "starting"
        self.last_run: datetime | None = None
        self.error: str | None = None
        self.mt5: MT5Connector | None = None

    def run(self):
        self.mt5 = MT5Connector(
            login    = int(self.cfg.mt5_login),
            password = self.cfg.mt5_password,
            server   = self.cfg.mt5_server,
        )
        ok, msg = self.mt5.connect()
        if not ok:
            self.status = "error"; self.error = msg; return

        self.status = "running"
        pairs = [p.strip() for p in self.cfg.pairs.split(",") if p.strip()]

        while not self._stop.is_set():
            try:
                self._cycle(pairs)
                self.last_run = datetime.utcnow()
                self.error    = None
            except Exception as e:
                self.error = str(e)
            self._stop.wait(60)

        self.mt5.disconnect()
        self.status = "stopped"

    def _cycle(self, pairs: list[str]):
        open_count = len(self.mt5.open_positions())
        if open_count >= self.cfg.max_trades:
            return

        acct = self.mt5.account_info()
        bal  = acct["balance"] if acct else 1000.0

        for symbol in pairs:
            if len(self.mt5.open_positions(symbol)) > 0:
                continue
            if len(self.mt5.open_positions()) >= self.cfg.max_trades:
                break

            candles = self.mt5.get_candles(symbol, self.cfg.timeframe)
            if not candles: continue

            tick = self.mt5.tick(symbol)
            if not tick: continue
            price = (tick[0] + tick[1]) / 2

            sig = combine(
                symbol = symbol,
                closes = candles["closes"],
                highs  = candles["highs"],
                lows   = candles["lows"],
                price  = price,
            )

            if sig.action == "HOLD" or sig.confidence < 0.3:
                continue

            sl_pips = abs(price - sig.stop_loss) / 0.00001
            lot     = self.mt5.calc_lot(symbol, sl_pips, bal, self.cfg.risk_pct)

            ok, ticket = self.mt5.open_order(
                symbol = symbol,
                action = sig.action,
                sl     = sig.stop_loss,
                tp     = sig.take_profit,
                lot    = lot,
            )

            if ok:
                self._log(symbol, sig, lot, price, ticket)

    def _log(self, symbol, sig, lot, price, ticket):
        with Session(engine) as s:
            s.add(TradeLog(
                session_token = self.token,
                symbol        = symbol,
                action        = sig.action,
                lot           = lot,
                price         = price,
                sl            = sig.stop_loss,
                tp            = sig.take_profit,
                confidence    = sig.confidence,
                reason        = " | ".join(
                    f"{k}: {v}" for k, v in sig.reasons.items()
                ),
                ticket        = int(ticket) if ticket.isdigit() else None,
            ))
            s.commit()

    def stop(self):
        self._stop.set()


# ── public API ────────────────────────────────────────────────

def start(token: str) -> dict:
    if token in _bots and _bots[token].status == "running":
        return {"ok": False, "msg": "Bot sudah jalan"}

    with Session(engine) as s:
        cfg = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()

    if not cfg:
        return {"ok": False, "msg": "Session tidak ditemukan"}
    if not cfg.pairs:
        return {"ok": False, "msg": "Belum pilih pair"}

    t = BotThread(token, cfg)
    t.start()
    _bots[token] = t

    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
        if row: row.is_active = True; s.add(row); s.commit()

    return {"ok": True, "msg": "Bot mulai berjalan"}


def stop(token: str) -> dict:
    t = _bots.pop(token, None)
    if t: t.stop()

    with Session(engine) as s:
        row = s.exec(select(TradingSession).where(TradingSession.session_token == token)).first()
        if row: row.is_active = False; s.add(row); s.commit()

    return {"ok": True, "msg": "Bot dihentikan"}


def status(token: str) -> dict:
    t = _bots.get(token)
    if not t:
        return {"status": "stopped", "last_run": None, "error": None}
    return {
        "status":   t.status,
        "last_run": t.last_run.isoformat() if t.last_run else None,
        "error":    t.error,
    }
