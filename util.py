import win32gui
import win32process
import win32api
import win32con


def get_active_window_exe():
    """
    Retrieves the executable path of the currently active (foreground) window.
    """
    try:
        # Get the handle of the foreground window
        hwnd = win32gui.GetForegroundWindow()
        # Get the process ID (PID) associated with the window
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # Open the process with necessary permissions
        hndl = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        # Get the executable path of the process
        path = win32process.GetModuleFileNameEx(hndl, 0)
        # Close the process handle
        win32api.CloseHandle(hndl)
        return path
    except Exception as e:
        print(f"Error getting active window executable: {e}")
        return None
