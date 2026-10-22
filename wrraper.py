import math
import threading
import MT5Manager

# =============================================================
# HELPERS
# =============================================================

def _last_error() -> str:
    """LastError() MT5Manager module ka function hai."""
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
            return int(modes.PUMP_MODE_FULL) # Fallback to Full
        result |= int(mode)
    return result


class MT5Service:

    def __init__(self):
        self.manager = None
        self._connected = False
        self._lock = threading.RLock()
        self._sink = None   

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

        # Simple login parsing logic for response visualization
        parsed_users = []
        for u in page:
            try:
                parsed_users.append({"Login": getattr(u, "Login", "N/A"), "Name": getattr(u, "Name", "N/A")})
            except:
                pass

        return {
            "total": total,
            "count": len(page),
            "offset": offset,
            "users": parsed_users,
        }
    # =========================================================
    # CUSTOM CLIENT API ENGINE (Via Manager Rights)
    # =========================================================
    def get_client_account_details(self, client_login: int):
        """
        Manager privileges ka use karke kisi bhi specific client ke account 
        ki live analytics (Balance, Equity, Margin, Leverage) fetch karein.
        """
        self._check_connection()

        with self._lock:
            # Server se real-time target account specifications request karein
            account_data = self._try("UserAccountRequest", int(client_login))
            
            if not account_data:
                raise KeyError(f"Client Account {client_login} details could not be retrieved: {_last_error()}")

            # Core dictionary mapping for client endpoints
            return {
                "login": getattr(account_data, "Login", client_login),
                "balance": getattr(account_data, "Balance", 0.0),
                "equity": getattr(account_data, "Equity", 0.0),
                "margin": getattr(account_data, "Margin", 0.0),
                "margin_free": getattr(account_data, "MarginFree", 0.0),
                "leverage": getattr(account_data, "Leverage", 0),
                "currency": getattr(account_data, "Currency", "USD")
            }
