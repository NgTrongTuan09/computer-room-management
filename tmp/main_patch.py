from utils.activity_db import init_db
from ui.activity_window import ActivityWindow

# Inside MainWindow.__init__ near server creation and start
init_db()

self.open_activity_windows = {}

# Modify button handlers where open_monitor is used; replace with open_activity_window
# Add method to MainWindow:

def open_activity_window(self, computer):
    existing = self.open_activity_windows.get(computer.client_id)
    if existing:
        existing.raise_()
        existing.activateWindow()
        return
    w = ActivityWindow(self, computer.client_id, computer.name, self.server)
    self.open_activity_windows[computer.client_id] = w
    
    def on_close(result=0, cid=computer.client_id):
        try:
            del self.open_activity_windows[cid]
        except KeyError:
            pass

    w.finished.connect(on_close)
    w.show()

# Then in create_card and add_computer_to_table replace btn clicked targets to open_activity_window
