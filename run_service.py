import os
import sys
import threading
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from wrraper import MT5Service  
from client_api import MT5ClientAPI  # Import our new C++ client engine layer

def start_cpp_bridge_listener(client_api_instance):
    """Real time thread logs read filters."""
    while True:
        try:
            event_data = client_api_instance.read_event()
            if event_data and event_data != "ERROR_READ_FAILED":
                print(f"📡 [C++ Live Tick Stream]: {event_data}")
            if event_data == "BRIDGE_OFFLINE":
                break
        except:
            break
        time.sleep(0.1)

def main():
    # ─── SECTION 1: REGULAR MANAGER SERVER CONNECTIVITY ───
    SERVER_IP = os.getenv("MT5_SERVER")
    MANAGER_LOGIN = os.getenv("MT5_LOGIN")
    MANAGER_PASSWORD = os.getenv("MT5_PASSWORD")
    PUMP_MODE = os.getenv("LIVE_PUMP", "FULL")

    print("🚀 Initializing MT5 Enterprise Manager API Layer...")
    manager_service = MT5Service()

    try:
        connection_result = manager_service.connect(
            server=SERVER_IP, login=int(MANAGER_LOGIN), password=MANAGER_PASSWORD, pump_mode=PUMP_MODE
        )
        print("✅ Manager API Connection Established Successfully!")
        
        if manager_service.connected():
            users_data = manager_service.list_users(group="*", limit=5, offset=0)
            print(f"📊 Database Active Accounts Registered: {users_data['total']}")

        # ─── SECTION 2: CLIENT API (C++ DLL BRIDGE TRIGGER) ───
        print("\n⚡ Initializing Custom C++ Client API Bridge Mechanism...")
        client_api = MT5ClientAPI(pipe_name="MT5_Python_Bridge")
        
        # Yeh function connection aane tak execution block rakhega (EA load hona zaroori h)
        if client_api.start_bridge():
            
            # Tick alerts monitoring ke liye extra parallel thread trigger karein
            listener_thread = threading.Thread(target=start_cpp_bridge_listener, args=(client_api,), daemon=True)
            listener_thread.start()
            
            # Real Time Target client transaction execution trigger karke check karein
            print("\n--- Sending Execution Alerts to Client Chart Terminal ---")
            TARGET_CLIENT_LOGIN = 1239574056387
            
            # Custom execution commands parsing string via Named Pipe inside C++ DLL
            client_api.send_action(f"BUY_ORDER:LOGIN={TARGET_CLIENT_LOGIN}:SYMBOL=EURUSD:VOL=0.1")
            
            # Core session active status loop check (5 seconds preview logs tracking)
            time.sleep(5)
            
            client_api.shutdown()

    except Exception as e:
        print(f"\n❌ Infrastructure Interrupted: {str(e)}")
    
    finally:
        if manager_service.connected():
            manager_service.disconnect()
            print("🔒 Manager core session closed safely.")

if __name__ == "__main__":
    main()
