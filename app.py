'''
Application to automatically change the volume of applications in Windows to a stored value
when the application window is in focus or loses focus. Useful for fully or partially muting
applications when the window moves to the background.
'''
import os
import psutil
import pygetwindow
import pythoncom
import threading
import tkinter
import queue
from tkinter import ttk
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from time import sleep
# Local Imports
from util import get_active_window_exe, db_execute


SQL_CREATE_TABLE = '''
      CREATE TABLE IF NOT EXISTS tbl_volume
      (
          id               INTEGER PRIMARY KEY,
          application_name TEXT UNIQUE,
          volume_fg   INTEGER DEFAULT 100,
          volume_bg   INTEGER DEFAULT 100
      );
      '''
SQL_GET_VOLUMES = 'SELECT volume_fg, volume_bg FROM tbl_volume WHERE application_name = ?;'
SQL_DELETE_APP = 'DELETE FROM tbl_volume WHERE application_name = ?;'
SQL_INSERT_APP = '''
    INSERT INTO tbl_volume (application_name, volume_fg, volume_bg)
        VALUES (?, ?, ?)
        ON CONFLICT(application_name) DO UPDATE SET
            volume_fg = excluded.volume_fg,
            volume_bg = excluded.volume_bg;
    '''

db_execute(SQL_CREATE_TABLE)


def get_volumes(app_name: str) -> tuple[int, int]:
    """Return (fg, bg) for an app, defaulting to (100, 100) if not stored."""
    rows = db_execute(SQL_GET_VOLUMES, (app_name,))
    return rows[0] if rows else (100, 100)


def set_volumes(app_name: str, fg: int, bg: int) -> None:
    db_execute(SQL_DELETE_APP, (app_name,))
    db_execute(SQL_INSERT_APP, (app_name, fg, bg))


class EditableTreeview(ttk.Treeview):

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<Double-1>", self._on_double_click)

    def _on_double_click(self, event):
        region = self.identify_region(event.x, event.y)
        if region == "cell":
            column_id = self.identify_column(event.x)
            # Allow only certain columns to be editable
            if column_id not in ['#2', '#3', ]:
                return
            row_id = self.identify_row(event.y)
            print(f'{column_id=}')
            print(f'{row_id=}')
            x, y, width, height = self.bbox(row_id, column_id)
            current_value = self.item(row_id, 'values')[int(column_id[1:]) - 1]
            application_name = self.item(row_id, 'values')[0]
            print(f'{application_name=}')
            # Create an Entry widget for editing
            entry = ttk.Entry(self, width=width // 10)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, current_value)
            entry.focus_set()

            def update_cell(event=None):
                new_value = entry.get()
                if column_id in ['#2', '#3', ]:
                    try:
                        if int(new_value) > 100:
                            new_value = '100'
                        if int(new_value) < 0:
                            new_value = '0'
                        self.set(row_id, column_id, new_value)
                        self.set(row_id, column_id, new_value)
                        volume_fg = int(self.item(row_id, 'values')[1])
                        volume_bg = int(self.item(row_id, 'values')[2])
                        set_volumes(application_name, volume_fg, volume_bg)
                    except ValueError:
                        pass
                entry.destroy()

            entry.bind("<Return>", update_cell)
            entry.bind("<FocusOut>", update_cell)


class App:

    tk_root: tkinter.Tk
    tk_tree: ttk.Treeview
    all_apps: dict

    def __init__(self):
        self.known_apps = set()        # only touched by the find_apps thread
        self.new_rows = queue.Queue()  # worker thread -> Tk thread
        self.init_tk()
        # daemon=True so closing the window actually exits the program
        threading.Thread(target=self.find_apps, daemon=True).start()
        threading.Thread(target=self.monitor_active_window, daemon=True).start()
        self.tk_root.after(200, self.poll_queue)
        self.tk_root.mainloop()  # blocks on the main thread

    def init_tk(self):
        self.tk_root = tkinter.Tk()
        self.tk_root.title('VolumeControl')
        tbl_cols = ['Application', 'Volume (FG)', 'Volume (BG)', ]
        self.tk_tree = EditableTreeview(self.tk_root, columns=tbl_cols, show='headings')
        for col in tbl_cols:
            self.tk_tree.heading(col, text=col)
        self.tk_tree.pack(expand=True, fill='both')

    def poll_queue(self):
        """Runs on the Tk thread: drain the queue and insert rows."""
        try:
            while True:
                row = self.new_rows.get_nowait()
                self.tk_tree.insert('', tkinter.END, values=row)
        except queue.Empty:
            pass
        self.tk_root.after(200, self.poll_queue)

    def find_apps(self):
        pythoncom.CoInitialize()
        while True:
            for session in AudioUtilities.GetAllSessions():
                try:
                    if not session.Process:
                        continue
                    name = session.Process.name()
                except psutil.Error:
                    continue
                if name not in self.known_apps:
                    self.known_apps.add(name)
                    fg, bg = get_volumes(name)
                    self.new_rows.put((name, fg, bg))  # no Tk calls here
            sleep(10)

    def apply_volumes(self, active_exe, last_exe):
        for session in AudioUtilities.GetAllSessions():
            try:
                if not session.Process:
                    continue
                name = session.Process.name()
            except psutil.Error:
                continue
            if name not in (active_exe, last_exe):
                continue
            fg, bg = get_volumes(name)
            new_volume = (fg if name == active_exe else bg) / 100
            print(f'setting {name} to {new_volume}')
            session.SimpleAudioVolume.SetMasterVolume(new_volume, None)

    def monitor_active_window(self):
        pythoncom.CoInitialize()
        last_title = None
        last_exe = ''
        last_pids = set()

        while True:
            window = pygetwindow.getActiveWindow()
            exe_path = get_active_window_exe() if window is not None else None
            if exe_path:
                active_exe = os.path.basename(exe_path)
                pids = {s.ProcessId for s in AudioUtilities.GetAllSessions()}
                if window.title != last_title or pids != last_pids:
                    self.apply_volumes(active_exe, last_exe)
                    last_title = window.title
                    last_pids = pids
                    last_exe = active_exe
            sleep(2 / 3)


if __name__ == '__main__':
    app = App()

