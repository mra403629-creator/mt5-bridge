# journal_check2.py
import os
import time
from dotenv import load_dotenv
from wrraper import MT5Service, _last_error

load_dotenv()
TARGETS = ("1000000000", "1239574057166")

s = MT5Service()
s.connect(os.getenv("MT5_SERVER"), int(os.getenv("MT5_LOGIN")), os.getenv("MT5_PASSWORD"))
try:
    m = s.manager
    now = int(time.time())
    start = now - 3 * 24 * 3600

    found = None
    for mode in range(0, 5):
        for typ in range(0, 5):
            try:
                res = m.LoggerServerRequest(mode, typ, start, now, "")
            except Exception as exc:
                print(f"mode={mode} type={typ}: exception {exc!r}")
                continue
            err = _last_error()
            kind = type(res).__name__
            size = len(res) if hasattr(res, "__len__") else "-"
            print(f"mode={mode} type={typ}: {kind} size={size} | {err}")
            if res and not isinstance(res, bool):
                found = (mode, typ, res)
                break
        if found:
            break

    if not found:
        print("Kisi bhi combination se records nahi aaye. Upar wale errors dekhein.")
    else:
        mode, typ, res = found
        recs = list(res)
        print(f"MIL GAYA: mode={mode} type={typ} total={len(recs)}")
        hits = [r for r in recs if any(t in str(r) for t in TARGETS)]
        print("target logins ki lines:", len(hits))
        for r in (hits or recs)[-20:]:
            print(r)
finally:
    s.disconnect()