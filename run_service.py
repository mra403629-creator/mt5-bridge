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
            print("\n--- Running Custom Client API Engine Call ---")
            
            # Yahan server database par maujood kisi bhi 1 real client ka login ID daalein (e.g., 77084)
            SAMPLE_CLIENT_ID = 77084  
            
            client_profile = service.get_client_account_details(client_login=SAMPLE_CLIENT_ID)
            print(f"👉 Target Client Balance: {client_profile['balance']} {client_profile['currency']}")
            print(f"👉 Target Client Equity : {client_profile['equity']}")
            print(f"👉 Target Client Leverage: 1:{client_profile['leverage']}")


    except Exception as e:
        print(f"\n❌ Server Connection Failed: {str(e)}")
    
    finally:
        if service.connected():
            service.disconnect()
            print("\n🔒 Connection closed safely.")

if __name__ == "__main__":
    main()
