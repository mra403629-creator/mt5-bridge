import os
import sys
from dotenv import load_dotenv

# Path synchronization
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load variables from .env
load_dotenv()

# Import the class engine we updated above
from wrraper import MT5Service  

def main():
    # Read variables from your live .env setup
    SERVER_IP = os.getenv("MT5_SERVER")
    MANAGER_LOGIN = os.getenv("MT5_LOGIN")
    MANAGER_PASSWORD = os.getenv("MT5_PASSWORD")
    PUMP_MODE = os.getenv("LIVE_PUMP", "FULL")

    print("🚀 Initializing MT5 Enterprise Manager API Layer...")
    service = MT5Service()

    try:
        print(f"🔗 Connecting securely to: {SERVER_IP} using Manager ID: {MANAGER_LOGIN}...")
        
        # Real-time handshake request to MT5 Hosting Server
        connection_result = service.connect(
            server=SERVER_IP,
            login=int(MANAGER_LOGIN),
            password=MANAGER_PASSWORD,
            pump_mode=PUMP_MODE
        )
        print("✅ Secure Connection Established Successfully!")
        print(f"Server System State: {connection_result}")

        # Live data pipeline testing check
        if service.connected():
            print("\n--- Running Active Session Check ---")
            users_data = service.list_users(group="*", limit=5, offset=0)
            print(f"Database Active Accounts Registered: {users_data['total']}")
                        # ─── USER KI REAL CLIENT ACCOUNT PIPELINE TESTING ───
        # Testing database connectivity
        if service.connected():
            print("\n--- Running Active Session Check ---")
            users_data = service.list_users(group="*", limit=5, offset=0)
            print(f"Database Active Accounts Registered: {users_data['total']}")

            # ─── EXECUTE CUSTOM CLIENT API ROUTE (YOUR NEW ENTRYPOINT) ───
            print("\n--- Triggering Custom Client API Trading Engine ---")
            
            # Aapka real validation client account variable
            TARGET_CLIENT_LOGIN = 1239574056387  
            
            try:
                # Hum is client login ID par 0.1 Lot ka market BUY execute kar rahe hain
                trade_receipt = service.execute_client_market_order(
                    client_login=TARGET_CLIENT_LOGIN,
                    symbol="EURUSD",  # Ya jo bhi commodity symbol aapke server par live ho
                    volume=0.1,
                    action_type="BUY"
                )
                print("=====================================================")
                print(f"🎯 CLIENT API STATUS: Live Position Deployed!")
                print(f"👉 Client Account Target : {trade_receipt['client']}")
                print(f"👉 Order Specifications : {trade_receipt['action']} - {trade_receipt['volume']} Lot {trade_receipt['symbol']}")
                print("=====================================================")
                
            except Exception as trade_err:
                print(f"❌ Client API Operation Interrupted: {str(trade_err)}")


    except Exception as e:
        print(f"\n❌ Server Connection Failed: {str(e)}")
    
    finally:
        if service.connected():
            service.disconnect()
            print("\n🔒 Connection closed safely.")

if __name__ == "__main__":
    main()
