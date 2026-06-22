import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QSplitter, QGraphicsOpacityEffect, QFrame, QMainWindow, QStackedWidget,
    QPushButton, QSlider, QGridLayout, QLayout
)
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QKeyEvent, QImage, QDrag
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint, QUrl,
    QEvent, QSize, QTimer, QMimeData
)

from config.constants import BG_COLOR, SCROLLBAR_BG, SCROLLBAR_HANDLE
from services.media_scanner import ImageWorker
from services.thumbnail_loader import ThumbnailLoader
from components.sidebar import ImageCard, SidebarListWidget
from components.detail_viewer import DetailViewer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Image Gallery")
        self.resize(1200, 800)
        self.setStyleSheet(f"background-color: {BG_COLOR.name()};")

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        self.detail_viewer = DetailViewer()
        self.detail_viewer.media_closed.connect(self.clear_selection)
        self.detail_viewer.image_clicked.connect(self.toggle_fullscreen)
        self.detail_viewer.fullscreen_requested.connect(self.enter_fullscreen)
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

        self.list_widget = SidebarListWidget()
        self.list_widget.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(10, 10, 10, 10)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.list_widget.selection_box_changed.connect(self.on_selection_box_changed)
        self.list_widget.selection_box_finished.connect(self.on_selection_box_changed)

        self.scroll_area.setWidget(self.list_widget)
        sidebar_layout.addWidget(self.scroll_area)

        self.scroll_area.verticalScrollBar().valueChanged.connect(self.trigger_lazy_load)

        self.splitter.addWidget(self.sidebar_container)
        self.splitter.setSizes([int(1200 * 0.7), int(1200 * 0.3)])

        self.cards = []
        self.current_index = -1

        # Initialize thumbnail loader
        self.thumb_loader = ThumbnailLoader()
        self.thumb_loader.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumb_loader.start()

        if getattr(sys, 'frozen', False):
            exec_dir = os.path.dirname(os.path.abspath(sys.executable))
            if "Contents/MacOS" in exec_dir:
                base_dir = os.path.abspath(os.path.join(exec_dir, "..", "..", ".."))
            else:
                base_dir = exec_dir
            
            # If the base_dir itself doesn't contain media folders but the parent does (e.g. windows exe/ folder),
            # use the parent folder.
            parent_dir = os.path.abspath(os.path.join(base_dir, ".."))
            has_media_subfolders = any(
                os.path.isdir(os.path.join(base_dir, sub))
                for sub in ["images", "videos", "pdf", "others"]
            )
            has_parent_media_subfolders = any(
                os.path.isdir(os.path.join(parent_dir, sub))
                for sub in ["images", "videos", "pdf", "others"]
            )
            if not has_media_subfolders and has_parent_media_subfolders:
                folder = parent_dir
            else:
                folder = base_dir
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            public_dir = os.path.join(base_dir, "public")
            folder = public_dir if os.path.exists(public_dir) else base_dir

        self.worker = ImageWorker(folder)
        self.worker.file_found.connect(self.add_image_card)
        self.worker.start()

        self.setMouseTracking(True)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def trigger_lazy_load(self):
        if not hasattr(self, 'cards') or not self.cards:
            return
        viewport_rect = self.scroll_area.viewport().rect()
        for card in self.cards:
            if not card.thumb_loaded:
                try:
                    top_left = card.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
                    bottom_right = card.mapTo(self.scroll_area.viewport(), QPoint(card.width(), card.height()))
                    card_rect = QRect(top_left, bottom_right)
                    if viewport_rect.intersects(card_rect):
                        card.thumb_loaded = True
                        self.thumb_loader.queue_request(card.filepath)
                except Exception:
                    pass

    def on_thumbnail_loaded(self, filepath, pixmap):
        for card in self.cards:
            if card.filepath == filepath:
                card.set_thumbnail(pixmap)
                break

    def add_image_card(self, filepath, filename, date_str):
        card = ImageCard(filepath, filename, date_str, self)
        card.clicked.connect(self.on_card_clicked)
        self.list_layout.addWidget(card)
        self.cards.append(card)

        if len(self.cards) == 1:
            self.select_card(0)

        QTimer.singleShot(50, self.trigger_lazy_load)

    def on_selection_box_changed(self, rect):
        modifiers = QApplication.keyboardModifiers()
        has_ctrl = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        has_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        for card in self.cards:
            card_rect = card.geometry()
            if rect.intersects(card_rect):
                card.set_selected(True)
            else:
                if not has_ctrl and not has_shift:
                    card.set_selected(False)
        print("Debug Box Selection: Selected cards:")
        for c in self.cards:
            if c.selected:
                print(f"  - {c.name_label.text()}")

    def clear_sidebar_selection(self):
        for card in self.cards:
            card.set_selected(False)

    def start_drag_operations(self, source_card):
        print("Selected before drag:")
        for c in self.cards:
            if c.selected:
                print(f"  - {c.name_label.text()}")

        selected_cards = [c for c in self.cards if c.selected]
        print(f"Debug Drag Start: Found {len(selected_cards)} selected cards to drag (source: {source_card.name_label.text()})")
        if not selected_cards:
            selected_cards = [source_card]

        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(c.filepath) for c in selected_cards]
        mime_data.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime_data)

        if selected_cards[0].thumb_label.pixmap():
            drag.setPixmap(selected_cards[0].thumb_label.pixmap())
            drag.setHotSpot(QPoint(40, 40))

        drag.exec_(Qt.DropAction.CopyAction)

        print("Selected after drag start:")
        for c in self.cards:
            if c.selected:
                print(f"  - {c.name_label.text()}")

    def clear_selection(self):
        if getattr(self, 'is_fullscreen', False):
            self.toggle_fullscreen()
        if self.current_index != -1:
            self.cards[self.current_index].set_selected(False)
            self.current_index = -1

    def toggle_fullscreen(self):
        if not hasattr(self, 'is_fullscreen'):
            self.is_fullscreen = False
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.sidebar_container.hide()
            self.showFullScreen()
        else:
            self.sidebar_container.show()
            self.showNormal()

    def enter_fullscreen(self):
        if not getattr(self, 'is_fullscreen', False):
            self.toggle_fullscreen()

    def eventFilter(self, watched, event):
        if getattr(self, 'is_fullscreen', False) and event.type() == QEvent.MouseMove:
            pos = self.mapFromGlobal(event.globalPos())
            w = self.width()
            if self.sidebar_container.isHidden():
                if pos.x() >= w - 80:
                    self.sidebar_container.show()
            else:
                if pos.x() < w - 300:
                    self.sidebar_container.hide()
        return super().eventFilter(watched, event)

    def on_card_clicked(self, filepath, card):
        modifiers = QApplication.keyboardModifiers()
        has_ctrl = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        has_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        index = self.cards.index(card)
        print(f"Debug on_card_clicked: {card.name_label.text()} (ctrl={has_ctrl}, shift={has_shift})")

        if has_ctrl:
            card.set_selected(not card.selected)
            if card.selected:
                self.current_index = index
        elif has_shift:
            if self.current_index != -1:
                start = min(self.current_index, index)
                end = max(self.current_index, index)
                for i, c in enumerate(self.cards):
                    c.set_selected(start <= i <= end)
            else:
                card.set_selected(True)
                self.current_index = index
        else:
            for c in self.cards:
                c.set_selected(c == card)
            self.current_index = index
            self.detail_viewer.load_media(filepath)

        print("Debug on_card_clicked: Selected cards:")
        for c in self.cards:
            if c.selected:
                print(f"  - {c.name_label.text()}")

    def select_card(self, index):
        if index < 0 or index >= len(self.cards):
            return

        if self.current_index != -1:
            self.cards[self.current_index].set_selected(False)

        self.current_index = index
        selected_card = self.cards[self.current_index]
        selected_card.set_selected(True)

        self.scroll_area.ensureWidgetVisible(selected_card)
        self.detail_viewer.load_media(selected_card.filepath)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            if getattr(self, 'is_fullscreen', False):
                self.toggle_fullscreen()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Up:
            if self.current_index > 0:
                self.select_card(self.current_index - 1)
        elif event.key() == Qt.Key.Key_Down:
            if self.current_index < len(self.cards) - 1:
                self.select_card(self.current_index + 1)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.trigger_lazy_load()

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.worker.stop()
        self.thumb_loader.stop()
        self.detail_viewer.shutdown()
        super().closeEvent(event)
