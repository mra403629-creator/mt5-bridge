import threading
import MT5Manager

# =============================================================
# HELPERS
# =============================================================

def _last_error() -> str:
    """MT5Manager.LastError() ka readable text."""
    try:
        code, retcode, message = MT5Manager.LastError()
        return f"[{code}] {retcode} - {message}"
    except Exception as exc:
        return f"unknown error ({exc})"


def _resolve_pump_mode(value):
    modes = MT5Manager.ManagerAPI.EnPumpModes
    if value is None or str(value).strip() == "":
        value = "FULL"

    text = str(value).strip().upper()
    if text in ("0", "NONE", "NO_PUMP"):
        return 0
    if text.isdigit():
        return int(text)

    result = 0
    for part in text.replace("+", "|").split("|"):
        part = part.strip()
        name = part if part.startswith("PUMP_MODE_") else f"PUMP_MODE_{part}"
        mode = getattr(modes, name, None)
        if mode is None:
            return int(modes.PUMP_MODE_FULL)  # Fallback to Full
        result |= int(mode)
    return result


def _search_roots():
    """Jin classes/modules mein enum constants dhoondhne hain."""
    roots = [MT5Manager]
    for name in ("MTRequest", "MTOrder", "MTPosition", "MTDeal", "ManagerAPI"):
        obj = getattr(MT5Manager, name, None)
        if obj is not None:
            roots.append(obj)
    return roots


def _find_const(names):
    """
    Constant (jaise TA_DEALER_POS_EXECUTE ya OP_BUY) ko MT5Manager ke andar
    khud dhoondhta hai: direct attribute, ya kisi nested enum class ke andar.
    Isse enum ka path galat hone par code nahi tootta.
    """
    if isinstance(names, str):
        names = (names,)

    for root in _search_roots():
        for name in names:
            if hasattr(root, name):
                return getattr(root, name)
        for attr in dir(root):
            if attr.startswith("_"):
                continue
            try:
                child = getattr(root, attr)
            except Exception:
                continue
            for name in names:
                try:
                    if hasattr(child, name):
                        return getattr(child, name)
                except Exception:
                    continue

    raise AttributeError(
        f"Constant {names} MT5Manager mein nahi mila. "
        f"service.diagnose() chalakar output bhejein."
    )


class _DealerSink:
    """Dealer ke jawab (result/answer) yahan aate hain."""

    def __init__(self):
        self.last = None
        self.event = threading.Event()

    def OnDealerResult(self, request, *args):
        self.last = ("result", request)
        self.event.set()

    def OnDealerAnswer(self, request, *args):
        self.last = ("answer", request)
        self.event.set()


class MT5Service:

    def __init__(self):
        self.manager = None
        self._connected = False
        self._lock = threading.RLock()
        self._sink = _DealerSink()
        self._dealer_started = False

    def connected(self):
        return self._connected

    # =========================================================
    # CONNECT METHOD
    # =========================================================
    def connect(
        self,
        server: str,
        login: int,
        password: str,
        timeout: int = 120000,
        pump_mode: str = "FULL",
    ):
        mode = _resolve_pump_mode(pump_mode)

        with self._lock:
            if self.manager:
                self._safe_disconnect()

            manager = MT5Manager.ManagerAPI()

            try:
                ok = manager.Connect(
                    server,
                    int(login),
                    password,
                    mode,
                    int(timeout),
                )
            except Exception as exc:
                raise RuntimeError(
                    f"MT5 Manager connection error: {exc} | {_last_error()}"
                )

            if not ok:
                error = _last_error()
                try:
                    manager.Disconnect()
                except Exception:
                    pass
                raise RuntimeError(f"MT5 Manager connection failed: {error}")

            self.manager = manager
            self._connected = True
            self._dealer_started = False

            return {
                "connected": True,
                "server": server,
                "login": login,
                "pump_mode": str(pump_mode).upper(),
            }

    def _safe_disconnect(self):
        if self.manager:
            try:
                self.manager.Disconnect()
            except Exception:
                pass
        self.manager = None
        self._connected = False
        self._dealer_started = False

    def disconnect(self):
        with self._lock:
            self._safe_disconnect()
        return {"connected": False}

    def _check_connection(self):
        if not self.manager or not self._connected:
            raise RuntimeError("MT5 Manager is not connected.")

    def _try(self, method: str, *args):
        try:
            return getattr(self.manager, method)(*args)
        except Exception:
            return None

    # =========================================================
    # DIAGNOSE (naam / enum check karne ke liye)
    # =========================================================
    def diagnose(self):
        """Ye chalakar poora output bhej dein agar koi naam match na ho."""
        print("--- ManagerAPI (Dealer/Order/Position/User) ---")
        print([n for n in dir(MT5Manager.ManagerAPI)
               if not n.startswith("_")
               and any(k in n for k in ("Dealer", "Order", "Position", "User", "Request"))])
        print("--- MTRequest fields ---")
        print([n for n in dir(MT5Manager.MTRequest) if not n.startswith("_")])
        print("--- Constants (TA_ / OP_ / ORDER_ / FILL) ---")
        for root in _search_roots():
            rname = getattr(root, "__name__", str(root))
            for attr in dir(root):
                if attr.startswith("_"):
                    continue
                try:
                    child = getattr(root, attr)
                except Exception:
                    continue
                if attr.startswith(("TA_", "OP_", "ORDER_", "FILL")):
                    print(f"{rname}.{attr}")
                else:
                    try:
                        inner = [n for n in dir(child)
                                 if n.startswith(("TA_", "OP_", "ORDER_TYPE", "ORDER_FILL"))]
                    except Exception:
                        inner = []
                    if inner:
                        print(f"{rname}.{attr}: {inner}")

    # =========================================================
    # USERS LIST METHOD
    # =========================================================
    def list_users(self, group: str = "*", limit: int = 10, offset: int = 0):
        self._check_connection()

        with self._lock:
            users = self._try("UserGetByGroup", group)
            if not users:
                users = self._try("UserRequestByGroup", group)

            if users is None or users is False:
                raise RuntimeError(f"Unable to get users: {_last_error()}")

            users_list = list(users)

        total = len(users_list)
        page = users_list[offset: offset + limit]

        parsed_users = []
        for u in page:
            try:
                parsed_users.append({
                    "Login": getattr(u, "Login", "N/A"),
                    "Name": getattr(u, "Name", "N/A"),
                })
            except Exception:
                pass

        return {
            "total": total,
            "count": len(page),
            "offset": offset,
            "users": parsed_users,
        }

    # =========================================================
    # CLIENT ACCOUNT DETAILS (Manager rights)
    # =========================================================
    def get_client_account_details(self, client_login: int):
        self._check_connection()

        with self._lock:
            account_data = self._try("UserAccountGet", int(client_login))
            if not account_data:
                account_data = self._try("UserAccountRequest", int(client_login))

            if not account_data:
                raise KeyError(
                    f"Client Account {client_login} details could not be retrieved: {_last_error()}"
                )

            return {
                "login": getattr(account_data, "Login", client_login),
                "balance": getattr(account_data, "Balance", 0.0),
                "equity": getattr(account_data, "Equity", 0.0),
                "margin": getattr(account_data, "Margin", 0.0),
                "margin_free": getattr(account_data, "MarginFree", 0.0),
                "leverage": getattr(account_data, "Leverage", 0),
                "currency": getattr(account_data, "Currency", "USD"),
            }

    # =========================================================
    # DEALER START (agar module mein available ho)
    # =========================================================
    def _ensure_dealer(self):
        if self._dealer_started:
            return
        start = getattr(self.manager, "DealerStart", None)
        if start is None:
            return  # is build mein DealerStart nahi hai, seedha DealerSend try hoga
        for args in ((self._sink,), ()):
            try:
                start(*args)
                self._dealer_started = True
                return
            except TypeError:
                continue
            except Exception as exc:
                raise RuntimeError(f"DealerStart failed: {exc!r} | {_last_error()}") from exc

    # =========================================================
    # CLIENT MARKET ORDER (Dealer route)
    # =========================================================
    def execute_client_market_order(self, client_login: int, symbol: str,
                                    volume: float, action_type: str = "BUY"):
        """
        Client ke account par dealer ki taraf se market order.
        Sirf DEMO account par 0.01 lot se test karein.
        """
        self._check_connection()

        with self._lock:
            side = action_type.upper()
            if side not in ("BUY", "SELL"):
                raise ValueError("action_type 'BUY' ya 'SELL' hona chahiye.")

            try:
                request = MT5Manager.MTRequest(self.manager)
            except Exception as exc:
                raise RuntimeError(f"MTRequest create failed: {exc!r} | {_last_error()}") from exc

            action = _find_const(("TA_DEALER_POS_EXECUTE",))
            order_type = _find_const(("OP_BUY",) if side == "BUY" else ("OP_SELL",))

            request.Login = int(client_login)
            request.Symbol = symbol
            request.Volume = int(round(volume * 10000))  # 1 lot = 10000
            request.Action = action
            request.Type = order_type

            # Fill type optional hai, mile to set kar dete hain
            try:
                request.TypeFill = _find_const(("ORDER_FILL_IOC", "FILL_IOC"))
            except Exception:
                pass

            self._ensure_dealer()
            self._sink.event.clear()

            ok = None
            last_exc = None
            for args in ((request, self._sink), (request,)):
                try:
                    ok = self.manager.DealerSend(*args)
                    break
                except TypeError as exc:
                    last_exc = exc
                    continue
                except AttributeError as exc:
                    raise RuntimeError(
                        "Is MT5Manager build mein DealerSend nahi hai. "
                        "service.diagnose() ka output bhejein."
                    ) from exc
                except Exception as exc:
                    raise RuntimeError(f"DealerSend failed: {exc!r} | {_last_error()}") from exc

            if ok is None and last_exc is not None:
                raise RuntimeError(f"DealerSend signature mismatch: {last_exc!r}") from last_exc

            if not ok:
                raise RuntimeError(f"Server rejected order: {_last_error()}")

            # Dealer jawab ka thoda intezaar (agar sink se aaye)
            self._sink.event.wait(3)

        return {
                "success": True,
                "client": client_login,
                "login": client_login,
                "symbol": symbol,
                "volume": volume,
                "action": side,
                "type": side,
                "dealer_reply": self._sink.last[0] if self._sink.last else "no callback received",
            }