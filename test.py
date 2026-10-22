
import MetaTrader5 as mt5

terminal_path = r"C:\Users\HP\AppData\Roaming\MetaTrader 5\terminal64.exe"

if not mt5.initialize(path=terminal_path):
    print("Initialization failed:", mt5.last_error())
else:
    print("MT5 initialized successfully")

    info = mt5.account_info()

    if info:
        print("Client Trade Server:", info.server)
        print("Login:", info.login)
    else:
        print("Account info unavailable:", mt5.last_error())

    mt5.shutdown()
