import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QLabel, QScrollArea, QGridLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QFileSystemWatcher


class ImageGallery(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Gallery")
        self.resize(1000, 700)

        self.main_layout = QVBoxLayout(self)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.scroll.setWidget(self.container)
        
        self.main_layout.addWidget(self.scroll)

        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        public_dir = os.path.join(base_dir, "public")
        self.folder = public_dir if os.path.exists(public_dir) else base_dir

        self.watcher = QFileSystemWatcher()
        self.watcher.addPath(self.folder)
        self.watcher.directoryChanged.connect(self.load_images)

        self.load_images()

    def load_images(self):
        # Clear existing widgets
        while self.grid.count():
            child = self.grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        try:
            image_files = [
                f for f in os.listdir(self.folder)
                if f.lower().endswith(
                    ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg')
                )
            ]
        except Exception:
            image_files = []

        row = 0
        col = 0

        for img in image_files:
            label = QLabel()

            pixmap = QPixmap(os.path.join(self.folder, img))
            pixmap = pixmap.scaled(
                250, 250,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.grid.addWidget(label, row, col)

            col += 1
            if col == 3:
                col = 0
                row += 1


app = QApplication(sys.argv)

window = ImageGallery()
window.show()

sys.exit(app.exec())