# try_servers.py
import os
import sys
import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv(override=True)

path = os.getenv("MT5_TERMINAL_PATH")
login = int(os.getenv("CLIENT_LOGIN"))
pwd = os.getenv("CLIENT_PASSWORD")
server = sys.argv[1] if len(sys.argv) > 1 else "AOne-Server"
portable = os.getenv("MT5_PORTABLE", "0") == "1"

print("path:", path)
print("login:", login, "| server:", server, "| portable:", portable)

ok = mt5.initialize(path=path, login=login, password=pwd, server=server,
                    timeout=60000, portable=portable)
print([s.name for s in mt5.symbols_get("*EURUSD*")][:5])
print("result:", ok, mt5.last_error())
if ok:
    print(mt5.account_info())
mt5.shutdown()