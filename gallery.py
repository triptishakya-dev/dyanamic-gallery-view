import os
import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QSplitter, QGraphicsOpacityEffect,
    QFrame, QMainWindow
)
from PyQt6.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QKeyEvent, QPainterPath
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, pyqtProperty, QPropertyAnimation, 
    QEasingCurve, QRect
)

# Dark theme colors
BG_COLOR = QColor("#121212")
CARD_BG = QColor("#2b2b2b")
CARD_HOVER = QColor("#3a3a3a")
CARD_SELECTED = QColor("#4a4a4a")
TEXT_COLOR = "#e0e0e0"
SCROLLBAR_BG = "#1e1e1e"
SCROLLBAR_HANDLE = "#555555"

class ImageWorker(QThread):
    thumbnail_ready = pyqtSignal(str, str, str, QPixmap)
    finished_loading = pyqtSignal()

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.running = True

    def run(self):
        try:
            files = [f for f in os.listdir(self.folder_path) 
                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg'))]
        except Exception:
            files = []
        
        files.sort()

        for filename in files:
            if not self.running:
                break
            filepath = os.path.join(self.folder_path, filename)
            try:
                stat = os.stat(filepath)
                dt = datetime.fromtimestamp(stat.st_ctime)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
                
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    size = min(pixmap.width(), pixmap.height())
                    rect = QRect((pixmap.width() - size) // 2, (pixmap.height() - size) // 2, size, size)
                    cropped = pixmap.copy(rect)
                    thumb = cropped.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    
                    rounded = QPixmap(80, 80)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addRoundedRect(0, 0, 80, 80, 8, 8)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, thumb)
                    painter.end()
                    
                    self.thumbnail_ready.emit(filepath, filename, date_str, rounded)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
                
        self.finished_loading.emit()

    def stop(self):
        self.running = False
        self.wait()

class ImageCard(QWidget):
    clicked = pyqtSignal(str, object)  # filepath, self

    def __init__(self, filepath, filename, date_str, thumbnail: QPixmap, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.selected = False
        self._bg_color = CARD_BG
        
        self.setFixedSize(280, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(80, 80)
        self.thumb_label.setPixmap(thumbnail)
        self.thumb_label.setStyleSheet("background-color: transparent;")
        
        layout.addWidget(self.thumb_label)
        
        text_layout = QVBoxLayout()
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        fm = self.fontMetrics()
        elided_name = fm.elidedText(filename, Qt.TextElideMode.ElideRight, 150)
        
        self.name_label = QLabel(elided_name)
        self.name_label.setStyleSheet(f"color: {TEXT_COLOR}; font-weight: bold; font-size: 14px; background: transparent;")
        
        self.date_label = QLabel(date_str)
        self.date_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.date_label)
        
        layout.addLayout(text_layout)
        
        self.anim = QPropertyAnimation(self, b"bgColor")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    @pyqtProperty(QColor)
    def bgColor(self):
        return self._bg_color

    @bgColor.setter
    def bgColor(self, color):
        self._bg_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._bg_color))
        if self.selected:
            painter.setPen(QPen(QColor("#777777"), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.filepath, self)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        if not self.selected:
            self.anim.stop()
            self.anim.setStartValue(self._bg_color)
            self.anim.setEndValue(CARD_HOVER)
            self.anim.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if not self.selected:
            self.anim.stop()
            self.anim.setStartValue(self._bg_color)
            self.anim.setEndValue(CARD_BG)
            self.anim.start()
        super().leaveEvent(event)

    def set_selected(self, selected):
        self.selected = selected
        self.anim.stop()
        if selected:
            self.bgColor = CARD_SELECTED
        else:
            self.bgColor = CARD_BG


class DetailViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #121212;")
        self.layout.addWidget(self.image_label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self.image_label)
        self.image_label.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self.current_pixmap = None

    def load_image(self, filepath):
        self.anim.stop()
        pixmap = QPixmap(filepath)
        self.current_pixmap = pixmap
        self.update_image()
        
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def update_image(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            scaled_pixmap = self.current_pixmap.scaled(
                self.image_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Image Gallery")
        self.resize(1200, 800)
        self.setStyleSheet(f"background-color: {BG_COLOR.name()};")
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)
        
        self.detail_viewer = DetailViewer()
        self.splitter.addWidget(self.detail_viewer)
        
        self.sidebar_container = QWidget()
        self.sidebar_container.setFixedWidth(300)
        self.sidebar_container.setStyleSheet("background-color: #1a1a1a; border-left: 1px solid #333;")
        
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {SCROLLBAR_BG};
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {SCROLLBAR_HANDLE};
                min-height: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #777777;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(10, 10, 10, 10)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.list_widget)
        sidebar_layout.addWidget(self.scroll_area)
        
        self.splitter.addWidget(self.sidebar_container)
        
        # Set 70/30 split ratio
        self.splitter.setSizes([int(1200 * 0.7), int(1200 * 0.3)])
        
        self.cards = []
        self.current_index = -1
        
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        public_dir = os.path.join(base_dir, "public")
        folder = public_dir if os.path.exists(public_dir) else base_dir
        
        self.worker = ImageWorker(folder)
        self.worker.thumbnail_ready.connect(self.add_image_card)
        self.worker.start()

    def add_image_card(self, filepath, filename, date_str, thumbnail):
        card = ImageCard(filepath, filename, date_str, thumbnail)
        card.clicked.connect(self.on_card_clicked)
        self.list_layout.addWidget(card)
        self.cards.append(card)
        
        if len(self.cards) == 1:
            self.select_card(0)

    def on_card_clicked(self, filepath, card):
        index = self.cards.index(card)
        self.select_card(index)

    def select_card(self, index):
        if index < 0 or index >= len(self.cards):
            return
            
        if self.current_index != -1:
            self.cards[self.current_index].set_selected(False)
            
        self.current_index = index
        selected_card = self.cards[self.current_index]
        selected_card.set_selected(True)
        
        self.scroll_area.ensureWidgetVisible(selected_card)
        self.detail_viewer.load_image(selected_card.filepath)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Up:
            if self.current_index > 0:
                self.select_card(self.current_index - 1)
        elif event.key() == Qt.Key.Key_Down:
            if self.current_index < len(self.cards) - 1:
                self.select_card(self.current_index + 1)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.worker.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())