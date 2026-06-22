import os
from datetime import datetime
# pyrefly: ignore [missing-import]
from PyQt5.QtCore import QThread, pyqtSignal
from config.constants import ALL_EXTS

class ImageWorker(QThread):
    file_found = pyqtSignal(str, str, str) # filepath, filename, date_str
    finished_loading = pyqtSignal()

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.running = True

    def stop(self):
        self.running = False
        self.requestInterruption()
        self.wait()

    def run(self):
        files_to_scan = [] # list of (filepath, filename)

        # Check for subfolders: images, videos, pdf, others
        subfolders = ["images", "videos", "pdf", "others"]
        has_subfolders = False
        for sub in subfolders:
            subpath = os.path.join(self.folder_path, sub)
            if os.path.isdir(subpath):
                has_subfolders = True
                break

        if has_subfolders:
            # Scan inside these subfolders
            for sub in subfolders:
                subpath = os.path.join(self.folder_path, sub)
                if os.path.isdir(subpath):
                    try:
                        for f in os.listdir(subpath):
                            if f.lower().endswith(ALL_EXTS):
                                files_to_scan.append((os.path.join(subpath, f), f))
                    except Exception as e:
                        print(f"Error reading subfolder {subpath}: {e}")
        else:
            # Fallback to the original behavior of scanning self.folder_path directly
            try:
                for f in os.listdir(self.folder_path):
                    if f.lower().endswith(ALL_EXTS):
                        files_to_scan.append((os.path.join(self.folder_path, f), f))
            except Exception as e:
                print(f"Error reading folder {self.folder_path}: {e}")

        # Sort the files by filename
        files_to_scan.sort(key=lambda x: x[1])

        for filepath, filename in files_to_scan:
            if not self.running:
                break
            try:
                stat = os.stat(filepath)
                dt = datetime.fromtimestamp(stat.st_ctime)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
                self.file_found.emit(filepath, filename, date_str)
            except Exception as e:
                print(f"Error scanning {filepath}: {e}")

        self.finished_loading.emit()
