# services/mt5_connector.py
# Wrapper tipis untuk MetaTrader5 — satu class per koneksi

import numpy as np
from typing import Optional

try:
    import MetaTrader5 as mt5
    MT5_OK = True
except ImportError:
    mt5    = None
    MT5_OK = False

TF_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}

class MT5Connector:
    def __init__(self, login: int, password: str, server: str):
        self.login    = login
        self.password = password
        self.server   = server

    def connect(self) -> tuple[bool, str]:
        if not MT5_OK:
            return False, "Library MetaTrader5 tidak tersedia di server ini. Gunakan mode demo."
        if not mt5.initialize():
            return False, f"MT5 initialize gagal: {mt5.last_error()}"
        if not mt5.login(self.login, self.password, self.server):
            mt5.shutdown()
            return False, f"Login gagal: {mt5.last_error()}"
        info = mt5.account_info()
        return True, f"OK|{info.balance}|{info.currency}|{info.server}"

    def disconnect(self):
        if MT5_OK: mt5.shutdown()

    def get_candles(self, symbol: str, tf: str = "H1", count: int = 300) -> Optional[dict]:
        if not MT5_OK: return None
        rates = mt5.copy_rates_from_pos(symbol, TF_MAP.get(tf, 16385), 0, count)
        if rates is None: return None
        return {
            "closes": np.array([r["close"] for r in rates]),
            "highs":  np.array([r["high"]  for r in rates]),
            "lows":   np.array([r["low"]   for r in rates]),
        }

    def tick(self, symbol: str) -> Optional[tuple[float, float]]:
        if not MT5_OK: return None
        t = mt5.symbol_info_tick(symbol)
        return (t.bid, t.ask) if t else None

    def spread(self, symbol: str) -> float:
        if not MT5_OK: return 0.0
        i = mt5.symbol_info(symbol); t = mt5.symbol_info_tick(symbol)
        return round((t.ask - t.bid) / i.point, 1) if i and t else 0.0

    def open_positions(self, symbol: str = None) -> list:
        if not MT5_OK: return []
        pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return list(pos) if pos else []

    def open_order(self, symbol: str, action: str, sl: float, tp: float, lot: float) -> tuple[bool, str]:
        if not MT5_OK: return False, "MT5 tidak tersedia"
        sym = mt5.symbol_info(symbol)
        t   = mt5.symbol_info_tick(symbol)
        if not sym or not t: return False, "Symbol tidak ditemukan"
        if not sym.visible: mt5.symbol_select(symbol, True)

        otype = mt5.ORDER_TYPE_BUY  if action == "BUY"  else mt5.ORDER_TYPE_SELL
        price = t.ask               if action == "BUY"  else t.bid

        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot,
            "type":         otype,
            "price":        price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        20250101,
            "comment":      "AutoTrader AI",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            return True, str(res.order)
        return False, f"Error {res.retcode}: {res.comment}"

    def calc_lot(self, symbol: str, sl_pips: float, balance: float, risk_pct: float) -> float:
        if not MT5_OK: return 0.01
        sym = mt5.symbol_info(symbol)
        if not sym: return 0.01
        pip_val = sym.trade_tick_value / sym.trade_tick_size * sym.point
        if pip_val == 0 or sl_pips == 0: return sym.volume_min
        lot = (balance * risk_pct) / (sl_pips * pip_val)
        lot = max(sym.volume_min, min(lot, sym.volume_max))
        return round(round(lot / sym.volume_step) * sym.volume_step, 2)

    def account_info(self) -> Optional[dict]:
        if not MT5_OK: return None
        a = mt5.account_info()
        return {"balance": a.balance, "equity": a.equity, "currency": a.currency} if a else None
