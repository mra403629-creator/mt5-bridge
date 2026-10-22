import os
from dotenv import load_dotenv
from wrraper import MT5Service
from group_api import GroupAPI

load_dotenv()

service = MT5Service()
# apne run_service.py wale hi variable names use karein
service.connect(
    os.getenv("MT5_SERVER"),
    int(os.getenv("MT5_LOGIN")),
    os.getenv("MT5_PASSWORD"),
)

g = GroupAPI(service)

try:
    print("GROUPS:", g.list_groups())
    print("SUMMARY:", g.group_summary("SK GROUP\\M8\\GROUP5"))
    

    # sirf jab upar wale dono sahi aa jayein, tab hi ye line chalayein
    # print(g.place_order(DEMO_ACCOUNT_LOGIN, "EURUSD", 0.01, "BUY"))
finally:
    service.disconnect()