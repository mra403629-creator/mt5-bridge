#property strict

// DLL Functions Import
#import "MT5ClientBridge.dll"
   bool InitializeBridge(string pipeName);
   bool WaitForClientConnection();
   bool SendCommand(string command);
   string ReadResponse();
   void CloseBridge();
#import

string pipe_name = "MT5_Python_Bridge";

int OnInit() {
    Print("Initializing C++ Client API Wrapper Bridge...");
    if(!InitializeBridge(pipe_name)) {
        Print("DLL Initialization Failed!");
        return(INIT_FAILED);
    }
    
    EventSetTimer(1); // Check pipe every 1 second
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    CloseBridge();
    EventKillTimer();
}

void OnTimer() {
    // Background listener for Python commands
    string request = ReadResponse();
    
    if(request != "ERROR_READ_FAILED" && request != "") {
        Print("Command Received from C++ Wrapper: ", request);
        
        // Execute Command Logic
        if(StringFind(request, "BUY") >= 0) {
            // Aapka Custom OrderSend() ya Client user request code yahan aayega
            // Example Response:
            SendCommand("SUCCESS: Order Executed");
        } 
        else if(request == "GET_BALANCE") {
            double balance = AccountInfoDouble(ACCOUNT_BALANCE);
            SendCommand("BALANCE:" + DoubleToString(balance, 2));
        }
    }
}

void OnTick() {
    // Real-time tick data streaming to Python via C++ Wrapper
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    string tick_data = "TICK:" + _Symbol + ":" + DoubleToString(bid, 5) + ":" + DoubleToString(ask, 5);
    SendCommand(tick_data);
}
