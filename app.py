'''
Application to automatically change the volume of applications in Windows to a stored value
when the application window is in focus or loses focus. Useful for fully or partially muting
applications when the window moves to the background.
'''
import psutil
import pygetwindow
import pythoncom
import threading
import tkinter
from tkinter import ttk
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from time import sleep
# Local Imports
from util import get_active_window_exe, db_execute


volume_table_create = '''
      CREATE TABLE IF NOT EXISTS tbl_volume
      (
          id               INTEGER PRIMARY KEY,
          application_name TEXT,
          volume_fg   INTEGER DEFAULT 100,
          volume_bg   INTEGER DEFAULT 100
      );
      '''
volume_table_update_1 = '''
    DELETE FROM tbl_volume WHERE application_name = "{0}";
    '''
volume_table_update_2 = '''
    INSERT INTO tbl_volume (application_name, volume_fg, volume_bg)
        VALUES ("{0}", {1}, {2});
    '''

db_execute(volume_table_create)


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
                        volume_fg = self.item(row_id, 'values')[1]
                        volume_bg = self.item(row_id, 'values')[2]
                        db_execute(volume_table_update_1.format(application_name))
                        db_execute(volume_table_update_2.format(application_name, volume_fg, volume_bg))
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
        thread_tk = threading.Thread(target=self.init_tk)
        thread_tk.start()
        self.all_apps = {}
        sleep(2)
        thread_find = threading.Thread(target=self.find_apps)
        thread_find.start()
        self.monitor_active_window()

    def init_tk(self):
        self.tk_root = tkinter.Tk()
        self.tk_root.title('VolumeControl')
        tbl_cols = ['Application', 'Volume (FG)', 'Volume (BG)', ]
        self.tk_tree = EditableTreeview(self.tk_root, columns=tbl_cols, show='headings')
        self.tk_tree.heading('Application', text='Application')
        self.tk_tree.heading('Volume (FG)', text='Volume (FG)')
        self.tk_tree.heading('Volume (BG)', text='Volume (BG)')
        self.tk_tree.pack(expand=True, fill='both')
        self.tk_root.mainloop()

    def find_apps(self):
        pythoncom.CoInitialize()
        while True:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    process_name = session.Process.name()
                    if process_name not in self.all_apps.keys():
                        query = f'SELECT * FROM tbl_volume WHERE application_name = "{process_name}";'
                        query_result = db_execute(query)
                        volume_fg = query_result[0][2] if query_result else 100
                        volume_bg = query_result[0][3] if query_result else 100
                        self.all_apps[process_name] = {
                            'session': session,
                            #'volume': volume,
                        }
                        self.tk_tree.insert('', tkinter.END, values=(process_name, volume_fg, volume_bg, ))
                        self.tk_tree.update_idletasks()
            sleep(10)

    def monitor_active_window(self):
        last_active_window = None
        while True:
            current_active_window = pygetwindow.getActiveWindow()
            if current_active_window is not None:
                current_window_title = current_active_window.title
                if current_window_title != last_active_window:
                    for key in self.all_apps.keys():
                        session = self.all_apps[key]['session']
                        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                        query = f'SELECT * FROM tbl_volume WHERE application_name = "{key}";'
                        query_result = db_execute(query)
                        if key == get_active_window_exe():
                            volume.SetMasterVolume(int(query_result[0][2])/100 if query_result else 1, None)
                        else:
                            volume.SetMasterVolume(int(query_result[0][3])/100 if query_result else 1, None)
                    last_active_window = current_window_title
            sleep(1)


if __name__ == '__main__':
    app = App()

