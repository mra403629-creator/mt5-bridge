"""
client_api.py  -  Direct CLIENT API (Manager API ke bina).

Client apne login / password / server se terminal ke through server par jaata hai.
Isme manager rights ya MT5Manager ki zaroorat nahi.

Requirements (Windows):
    pip install MetaTrader5 python-dotenv
    MT5 terminal installed hona chahiye (terminal64.exe)

.env:
    MT5_SERVER=access.tgshost.org:43143      # ya server ka naam jo terminal mein dikhta hai
    MT5_TERMINAL_PATH=C:\\Program Files\\MetaTrader 5\\terminal64.exe
    CLIENT_LOGIN=<client login>
    CLIENT_PASSWORD=<client password>
    MAX_LOT=0.1

IMPORTANT:
  * MetaTrader5 module ek process mein EK hi terminal / EK hi login sambhalta hai.
    Isliye ye class ek process = ek client session ke liye hai.
  * Pehle DEMO account par 0.01 lot se test karein.
"""

import os
import threading
from datetime import datetime, timedelta

import MetaTrader5 as mt5


class MT5ClientError(RuntimeError):
    pass


def _err() -> str:
    try:
        code, msg = mt5.last_error()
        return f"[{code}] {msg}"
    except Exception as exc:
        return f"unknown error ({exc})"


class MT5ClientSession:
    """Ek client ka direct session (apne credentials se)."""

    def __init__(self, max_lot: float = None):
        self._lock = threading.RLock()
        self._connected = False
        self.max_lot = float(max_lot if max_lot is not None else os.getenv("MAX_LOT", "0.1"))

    # ---------------------------------------------------------
    # CONNECT / DISCONNECT
    # ---------------------------------------------------------
    def connect(self, login: int, password: str, server: str,
                terminal_path: str = None, timeout: int = 60000):
        with self._lock:
            kwargs = dict(login=int(login), password=password, server=server, timeout=timeout)
            if terminal_path:
                kwargs["path"] = terminal_path

            if not mt5.initialize(**kwargs):
                raise MT5ClientError(f"Client login failed: {_err()}")

            info = mt5.account_info()
            if info is None:
                mt5.shutdown()
                raise MT5ClientError(f"Login hua par account info nahi mili: {_err()}")

            self._connected = True
            return {"connected": True, "login": info.login, "server": info.server,
                    "name": info.name, "currency": info.currency}

    def disconnect(self):
        with self._lock:
            mt5.shutdown()
            self._connected = False
        return {"connected": False}

    def _check(self):
        if not self._connected:
            raise MT5ClientError("Client session connected nahi hai.")

    # ---------------------------------------------------------
    # ACCOUNT
    # ---------------------------------------------------------
    def account(self):
        self._check()
        with self._lock:
            a = mt5.account_info()
            if a is None:
                raise MT5ClientError(f"account_info failed: {_err()}")
            return {
                "login": a.login, "name": a.name, "server": a.server,
                "balance": a.balance, "equity": a.equity,
                "margin": a.margin, "margin_free": a.margin_free,
                "leverage": a.leverage, "currency": a.currency,
                "profit": a.profit,
            }

    # ---------------------------------------------------------
    # POSITIONS
    # ---------------------------------------------------------
    def positions(self, symbol: str = None):
        self._check()
        with self._lock:
            res = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if res is None:
                raise MT5ClientError(f"positions_get failed: {_err()}")
            return [{
                "ticket": p.ticket, "symbol": p.symbol,
                "side": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": p.volume, "price_open": p.price_open,
                "price_current": p.price_current, "sl": p.sl, "tp": p.tp,
                "profit": p.profit, "comment": p.comment,
            } for p in res]

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------
    @staticmethod
    def _filling(symbol: str):
        info = mt5.symbol_info(symbol)
        mode = getattr(info, "filling_mode", 0) if info else 0
        if mode & 2:
            return mt5.ORDER_FILLING_IOC
        if mode & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    @staticmethod
    def _result(res, what: str):
        if res is None:
            raise MT5ClientError(f"{what}: order_send None return kiya: {_err()}")
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            raise MT5ClientError(f"{what} reject: retcode={res.retcode} comment={res.comment}")
        return {"retcode": res.retcode, "order": res.order, "deal": res.deal,
                "volume": res.volume, "price": res.price, "comment": res.comment}

    # ---------------------------------------------------------
    # OPEN MARKET ORDER
    # ---------------------------------------------------------
    def open_order(self, symbol: str, volume: float, side: str = "BUY",
                   sl: float = 0.0, tp: float = 0.0, deviation: int = 20,
                   comment: str = "client-api"):
        self._check()
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError("side 'BUY' ya 'SELL' hona chahiye.")
        if volume <= 0 or volume > self.max_lot:
            raise ValueError(f"Volume {volume} allowed range (0 - {self.max_lot}) ke bahar hai.")

        with self._lock:
            if not mt5.symbol_select(symbol, True):
                raise MT5ClientError(f"Symbol '{symbol}' select nahi hua: {_err()}")
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise MT5ClientError(f"Tick nahi mila: {_err()}")

            is_buy = side == "BUY"
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": tick.ask if is_buy else tick.bid,
                "sl": float(sl), "tp": float(tp),
                "deviation": int(deviation),
                "magic": 20260101,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._filling(symbol),
            }
            return self._result(mt5.order_send(request), f"{side} {symbol}")

    # ---------------------------------------------------------
    # CLOSE POSITION
    # ---------------------------------------------------------
    def close_position(self, ticket: int):
        self._check()
        with self._lock:
            pos = mt5.positions_get(ticket=int(ticket))
            if not pos:
                raise MT5ClientError(f"Position {ticket} nahi mili.")
            p = pos[0]
            tick = mt5.symbol_info_tick(p.symbol)
            if tick is None:
                raise MT5ClientError(f"Tick nahi mila: {_err()}")

            closing_buy = p.type == mt5.POSITION_TYPE_SELL  # sell band karne ke liye buy
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": mt5.ORDER_TYPE_BUY if closing_buy else mt5.ORDER_TYPE_SELL,
                "position": p.ticket,
                "price": tick.ask if closing_buy else tick.bid,
                "deviation": 20,
                "magic": 20260101,
                "comment": "client-api close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._filling(p.symbol),
            }
            return self._result(mt5.order_send(request), f"close {ticket}")

    # ---------------------------------------------------------
    # MODIFY SL / TP
    # ---------------------------------------------------------
    def modify_sltp(self, ticket: int, sl: float = None, tp: float = None):
        self._check()
        with self._lock:
            pos = mt5.positions_get(ticket=int(ticket))
            if not pos:
                raise MT5ClientError(f"Position {ticket} nahi mili.")
            p = pos[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": p.symbol,
                "position": p.ticket,
                "sl": float(p.sl if sl is None else sl),
                "tp": float(p.tp if tp is None else tp),
            }
            return self._result(mt5.order_send(request), f"modify {ticket}")

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------
    def history(self, days: int = 7):
        self._check()
        with self._lock:
            now = datetime.now()
            deals = mt5.history_deals_get(now - timedelta(days=days), now)
            if deals is None:
                raise MT5ClientError(f"history_deals_get failed: {_err()}")
            return [{
                "ticket": d.ticket, "order": d.order, "symbol": d.symbol,
                "type": d.type, "volume": d.volume, "price": d.price,
                "profit": d.profit, "time": datetime.fromtimestamp(d.time).isoformat(),
            } for d in deals]


# run_service.py is naam se import karta hai
MT5ClientAPI = MT5ClientSession


# =============================================================
# QUICK TEST   ->   python client_api.py
# =============================================================
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    s = MT5ClientSession()
    try:
        print("CONNECT:", s.connect(
            login=int(os.getenv("CLIENT_LOGIN")),
            password=os.getenv("CLIENT_PASSWORD"),
            server=os.getenv("CLIENT_SERVER") or os.getenv("MT5_SERVER"),
            terminal_path=os.getenv("MT5_TERMINAL_PATH"),
        ))
        print("ACCOUNT:", s.account())
        print("POSITIONS:", s.positions())

        # Order test: sirf DEMO account par, comment hata kar chalayein
        # print("ORDER:", s.open_order("EURUSD", 0.01, "BUY"))
    finally:
        s.disconnect()