import sqlite3
import win32gui
import win32process
import win32api
import win32con
from contextlib import closing


def get_active_window_exe():
    """
    Retrieves the executable path of the currently active (foreground) window.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        hndl = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        path = win32process.GetModuleFileNameEx(hndl, 0)
        win32api.CloseHandle(hndl)
        return path
    except Exception as e:
        print(f"Error getting active window executable: {e}")
        return None


def db_execute(query: str, params: tuple = ()):
    with closing(sqlite3.connect('volume_control.db')) as conn:
        with conn:  # commits on success, rolls back on error
            return conn.execute(query, params).fetchall()
