#include <windows.h>
#include <iostream>
#include <string>

#define EXPORT extern "C" __declspec(dllexport)

HANDLE hPipe = INVALID_HANDLE_VALUE;

// 1. Initialize Named Pipe Server (MT5 EA se connect karne ke liye)
EXPORT bool InitializeBridge(const char* pipeName) {
    std::string fullPipeName = "\\\\.\\pipe\\" + std::string(pipeName);
    
    hPipe = CreateNamedPipeA(
        fullPipeName.c_str(),
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES,
        1024, 1024, 0, NULL
    );

    if (hPipe == INVALID_HANDLE_VALUE) return false;
    return true;
}

// 2. Wait for MT5 Terminal (EA) to Connect
EXPORT bool WaitForClientConnection() {
    if (hPipe == INVALID_HANDLE_VALUE) return false;
    return ConnectNamedPipe(hPipe, NULL) ? true : (GetLastError() == ERROR_PIPE_CONNECTED);
}

// 3. Send Command from Python/C++ to MT5 Terminal
EXPORT bool SendCommand(const char* command) {
    if (hPipe == INVALID_HANDLE_VALUE) return false;
    DWORD bytesWritten;
    return WriteFile(hPipe, command, (DWORD)strlen(command), &bytesWritten, NULL);
}

// 4. Read Response/Ticks from MT5 Terminal
EXPORT const char* ReadResponse() {
    static char buffer[1024];
    memset(buffer, 0, sizeof(buffer));
    DWORD bytesRead;
    
    if (ReadFile(hPipe, buffer, sizeof(buffer) - 1, &bytesRead, NULL)) {
        return buffer;
    }
    return "ERROR_READ_FAILED";
}

// 5. Close Connection
EXPORT void CloseBridge() {
    if (hPipe != INVALID_HANDLE_VALUE) {
        DisconnectNamedPipe(hPipe);
        CloseHandle(hPipe);
    }
}
