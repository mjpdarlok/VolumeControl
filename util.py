import sqlite3
import win32gui
import win32process
import win32api
import win32con


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


def db_execute(query: str):
    db_conn = sqlite3.connect('volume_control.db')
    db_cursor = db_conn.cursor()
    db_cursor.execute(query)
    db_conn.commit()
    result = db_cursor.fetchall()
    db_cursor.close()
    db_conn.close()
    return result
