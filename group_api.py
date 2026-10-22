"""
group_api.py  -  Group-wise structure for the MT5 client API.

Isko wrraper.py ke saath usi folder mein rakhein.

Use:
    from wrraper import MT5Service
    from group_api import GroupAPI

    service = MT5Service()
    service.connect(...)
    groups = GroupAPI(service)

    groups.list_groups()
    groups.group_users("demo\\*", limit=20)
    groups.group_summary("demo\\retail")
    groups.group_positions("demo\\retail")
    groups.place_order(1239574056387, "EURUSD", 0.01, "BUY")   # group policy ke saath

.env mein (optional):
    ALLOWED_GROUPS=demo\\*,real\\retail      # comma separated, * wildcard chalta hai
    ALLOWED_SYMBOLS=EURUSD,GBPUSD,XAUUSD     # khali = sab allowed
    MAX_LOT=0.1                              # ek order ki max volume
"""

import fnmatch
import os

import MT5Manager


def _split_env(name: str):
    raw = os.getenv(name, "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


class GroupPolicy:
    """Kaunse group par kaam allowed hai, kaunse symbol, kitni max volume."""

    def __init__(self, allowed_groups=None, allowed_symbols=None, max_lot=None):
        self.allowed_groups = allowed_groups if allowed_groups is not None else _split_env("ALLOWED_GROUPS")
        self.allowed_symbols = allowed_symbols if allowed_symbols is not None else _split_env("ALLOWED_SYMBOLS")
        self.max_lot = float(max_lot if max_lot is not None else os.getenv("MAX_LOT", "0.1"))

    def group_allowed(self, group: str) -> bool:
        if not self.allowed_groups:
            return False  # default: kuch bhi allowed nahi, jab tak .env mein na likha ho
        g = (group or "").lower()
        return any(fnmatch.fnmatch(g, pat.lower()) for pat in self.allowed_groups)

    def symbol_allowed(self, symbol: str) -> bool:
        if not self.allowed_symbols:
            return True
        return symbol.upper() in {s.upper() for s in self.allowed_symbols}


class GroupAPI:

    def __init__(self, service, policy: GroupPolicy = None):
        self.service = service
        self.policy = policy or GroupPolicy()

    # ---------------------------------------------------------
    # internal helpers
    # ---------------------------------------------------------
    def _mgr(self):
        self.service._check_connection()
        return self.service.manager

    def _call_first(self, names, *args):
        """Pehla method jo chal jaye uska result. Sab fail hon to saaf error."""
        mgr = self._mgr()
        errors = []
        for name in names:
            fn = getattr(mgr, name, None)
            if fn is None:
                errors.append(f"{name}: missing")
                continue
            try:
                res = fn(*args)
                if res is not None and res is not False:
                    return res
                errors.append(f"{name}: returned {res!r}")
            except Exception as exc:
                errors.append(f"{name}: {exc!r}")
        raise RuntimeError("Koi bhi method nahi chala -> " + " | ".join(errors))

    def client_group(self, login: int) -> str:
        """Client ka group naam."""
        user = self._call_first(("UserGet", "UserRequest"), int(login))
        return str(getattr(user, "Group", ""))

    # ---------------------------------------------------------
    # GROUPS
    # ---------------------------------------------------------
    def list_groups(self):
        mgr = self._mgr()
        names = []
        total = getattr(mgr, "GroupTotal", None)
        nxt = getattr(mgr, "GroupNext", None)
        if total is None or nxt is None:
            raise RuntimeError("GroupTotal/GroupNext is build mein nahi mile. dir(ManagerAPI) check karein.")

        for i in range(int(total())):
            g = nxt(i)
            if g is not None:
                names.append(str(getattr(g, "Group", g)))

        return {
            "total": len(names),
            "groups": names,
            "allowed_by_policy": [n for n in names if self.policy.group_allowed(n)],
        }

    # ---------------------------------------------------------
    # USERS IN GROUP
    # ---------------------------------------------------------
    def group_users(self, group: str, limit: int = 50, offset: int = 0):
        return self.service.list_users(group=group, limit=limit, offset=offset)

    # ---------------------------------------------------------
    # GROUP SUMMARY (balance / equity / margin ka total)
    # ---------------------------------------------------------
    def group_summary(self, group: str, max_accounts: int = 200):
        total = {"group": group, "accounts": 0, "balance": 0.0,
                    "equity": 0.0, "margin": 0.0, "margin_free": 0.0, "note": ""}

        accounts = None
        try:
            accounts = self._call_first(
                ("UserAccountGetByGroup", "UserAccountRequestByGroup"), group
            )
        except RuntimeError:
            accounts = None

        if accounts is None:
            # fallback: group ke users -> har ka account alag se
            users = self.service.list_users(group=group, limit=max_accounts, offset=0)
            accounts = []
            for u in users["users"]:
                try:
                    acc = self._call_first(("UserAccountGet", "UserAccountRequest"),
                                            int(u["Login"]))
                    accounts.append(acc)
                except Exception:
                    continue
            if users["total"] > max_accounts:
                total["note"] = f"Sirf pehle {max_accounts} / {users['total']} accounts count hue."

        for acc in list(accounts):
            total["accounts"] += 1
            total["balance"] += float(getattr(acc, "Balance", 0.0))
            total["equity"] += float(getattr(acc, "Equity", 0.0))
            total["margin"] += float(getattr(acc, "Margin", 0.0))
            total["margin_free"] += float(getattr(acc, "MarginFree", 0.0))
        return total

    # ---------------------------------------------------------
    # POSITIONS IN GROUP
    # ---------------------------------------------------------
    def group_positions(self, group: str, limit: int = 100):
        positions = self._call_first(
            ("PositionGetByGroup", "PositionRequestByGroup"), group
        )
        out = []
        for p in list(positions)[:limit]:
            out.append({
                "ticket": getattr(p, "Position", None),
                "login": getattr(p, "Login", None),
                "symbol": getattr(p, "Symbol", None),
                "volume": getattr(p, "Volume", None),
                "action": getattr(p, "Action", None),
                "price_open": getattr(p, "PriceOpen", None),
                "profit": getattr(p, "Profit", None),
            })
        return {"group": group, "count": len(out), "positions": out}

    # ---------------------------------------------------------
    # GUARDED ORDER  (group + symbol + volume check ke baad hi order)
    # ---------------------------------------------------------
    def place_order(self, client_login: int, symbol: str, volume: float, action_type: str = "BUY"):
        group = self.client_group(client_login)

        if not self.policy.group_allowed(group):
            raise PermissionError(
                f"Group '{group}' allowed nahi hai. .env mein ALLOWED_GROUPS set karein."
            )
        if not self.policy.symbol_allowed(symbol):
            raise PermissionError(f"Symbol '{symbol}' allowed nahi hai.")
        if volume <= 0 or volume > self.policy.max_lot:
            raise ValueError(f"Volume {volume} allowed range (0 - {self.policy.max_lot}) ke bahar hai.")

        receipt = self.service.execute_client_market_order(client_login, symbol, volume, action_type)
        receipt["group"] = group
        return receipt