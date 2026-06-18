import os
import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QSplitter, QGraphicsOpacityEffect,
    QFrame, QMainWindow, QStackedWidget, QPushButton, QSlider,
    QPinchGesture, QGridLayout, QLayout
)
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QKeyEvent, QPainterPath,
    QLinearGradient, QPolygon, QImage, QDrag
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, pyqtProperty, QPropertyAnimation, 
    QEasingCurve, QRect, QPoint, QUrl, QEvent, QMutex, QWaitCondition,
    QSize, QTimer, QMimeData
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import fitz


# Dark theme colors
BG_COLOR = QColor("#121212")
CARD_BG = QColor("#2b2b2b")
CARD_HOVER = QColor("#3a3a3a")
CARD_SELECTED = QColor("#4a4a4a")
TEXT_COLOR = "#ffffff"
SCROLLBAR_BG = "#1e1e1e"
SCROLLBAR_HANDLE = "#555555"

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg')
VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.webm')
PDF_EXTS = ('.pdf',)
ALL_EXTS = IMAGE_EXTS + VIDEO_EXTS + PDF_EXTS


class ImageWorker(QThread):
    file_found = pyqtSignal(str, str, str) # filepath, filename, date_str
    finished_loading = pyqtSignal()

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.running = True

    def run(self):
        try:
            files = [f for f in os.listdir(self.folder_path) 
                     if f.lower().endswith(ALL_EXTS)]
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
                self.file_found.emit(filepath, filename, date_str)
            except Exception as e:
                print(f"Error scanning {filepath}: {e}")
                
        self.finished_loading.emit()


class ThumbnailLoader(QThread):
    thumbnail_loaded = pyqtSignal(str, QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        self.queue_lock = QMutex()
        self.running = True
        self.condition = QWaitCondition()
        self.cache = {}

    def queue_request(self, filepath):
        self.queue_lock.lock()
        if filepath in self.cache:
            self.thumbnail_loaded.emit(filepath, self.cache[filepath])
            self.queue_lock.unlock()
            return
            
        if filepath not in self.queue:
            self.queue.append(filepath)
            self.condition.wakeOne()
        self.queue_lock.unlock()

    def stop(self):
        self.running = False
        self.condition.wakeOne()
        self.wait()

    def run(self):
        while self.running:
            self.queue_lock.lock()
            while not self.queue and self.running:
                self.condition.wait(self.queue_lock)
            if not self.running:
                self.queue_lock.unlock()
                break
            filepath = self.queue.pop(0)
            self.queue_lock.unlock()

            pixmap = self.load_thumb(filepath)
            if pixmap:
                self.queue_lock.lock()
                self.cache[filepath] = pixmap
                self.queue_lock.unlock()
                self.thumbnail_loaded.emit(filepath, pixmap)

    def load_thumb(self, filepath):
        lower_name = filepath.lower()
        if lower_name.endswith(IMAGE_EXTS):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                return self.create_rounded_thumbnail(pixmap)
        elif lower_name.endswith(PDF_EXTS):
            try:
                doc = fitz.open(filepath)
                if len(doc) > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                    fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
                    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                    pixmap = QPixmap.fromImage(qimg)
                    return self.create_rounded_thumbnail(pixmap)
            except Exception as e:
                print(f"Error making PDF thumbnail: {e}")
        elif lower_name.endswith(VIDEO_EXTS):
            return self.create_video_placeholder()
        return None

    def create_rounded_thumbnail(self, pixmap):
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
        return rounded

    def create_video_placeholder(self):
        rounded = QPixmap(80, 80)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, 80, 80, 8, 8)
        painter.setClipPath(path)
        
        grad = QLinearGradient(0, 0, 80, 80)
        grad.setColorAt(0, QColor("#1e293b"))
        grad.setColorAt(1, QColor("#0f172a"))
        painter.fillRect(0, 0, 80, 80, QBrush(grad))
        
        painter.setBrush(QBrush(QColor("#38bdf8")))
        painter.setPen(Qt.PenStyle.NoPen)
        
        poly = QPolygon([
            QPoint(32, 28),
            QPoint(32, 52),
            QPoint(54, 40)
        ])
        painter.drawPolygon(poly)
        painter.end()
        return rounded


class ImageCard(QWidget):
    clicked = pyqtSignal(str, object)  # filepath, self

    def __init__(self, filepath, filename, date_str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.selected = False
        self._bg_color = CARD_BG
        self.thumb_loaded = False
        
        self.setFixedSize(280, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(80, 80)
        
        # Set initial rounded placeholder
        placeholder = QPixmap(80, 80)
        placeholder.fill(Qt.GlobalColor.transparent)
        painter = QPainter(placeholder)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#333333"), 2))
        painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.drawRoundedRect(1, 1, 78, 78, 8, 8)
        painter.end()
        self.thumb_label.setPixmap(placeholder)
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

    def set_thumbnail(self, pixmap):
        self.thumb_label.setPixmap(pixmap)
        self.thumb_loaded = True

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
            painter.setPen(QPen(QColor("#38bdf8"), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    def get_mainwindow(self):
        p = self.parent()
        while p:
            if isinstance(p, QMainWindow):
                return p
            p = p.parent()
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.mouse_pressed_selected = self.selected
            
            modifiers = QApplication.keyboardModifiers()
            has_mod = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier))
            
            print(f"Debug Card Press: {self.name_label.text()} (selected={self.selected}, has_mod={has_mod})")
            if self.selected and not has_mod:
                print(f"Debug Card Press: Deferring click emission for {self.name_label.text()}")
                pass
            else:
                self.clicked.emit(self.filepath, self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if hasattr(self, 'drag_start_pos'):
                if (event.pos() - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                    if self.selected:
                        mw = self.get_mainwindow()
                        if mw:
                            mw.start_drag_operations(self)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'drag_start_pos'):
                diff = (event.pos() - self.drag_start_pos).manhattanLength()
                print(f"Debug Card Release: {self.name_label.text()} (drag_diff={diff})")
                if diff < QApplication.startDragDistance():
                    modifiers = QApplication.keyboardModifiers()
                    has_mod = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier))
                    if self.selected and not has_mod and getattr(self, 'mouse_pressed_selected', False):
                        print(f"Debug Card Release: Triggering deferred click for {self.name_label.text()}")
                        self.clicked.emit(self.filepath, self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
        
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


class SidebarListWidget(QWidget):
    selection_box_changed = pyqtSignal(QRect)
    selection_box_finished = pyqtSignal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rubber_band = None
        self.origin = QPoint()
        self.setMouseTracking(True)
        
    def get_mainwindow(self):
        p = self.parent()
        while p:
            if isinstance(p, QMainWindow):
                return p
            p = p.parent()
        return None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            if not self.rubber_band:
                from PyQt5.QtWidgets import QRubberBand
                self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            
            modifiers = QApplication.keyboardModifiers()
            has_mod = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier))
            if not has_mod:
                mw = self.get_mainwindow()
                if mw:
                    mw.clear_sidebar_selection()
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if self.rubber_band and self.rubber_band.isVisible():
            rect = QRect(self.origin, event.pos()).normalized()
            self.rubber_band.setGeometry(rect)
            self.selection_box_changed.emit(rect)
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        if self.rubber_band and self.rubber_band.isVisible():
            self.rubber_band.hide()
            rect = QRect(self.origin, event.pos()).normalized()
            self.selection_box_finished.emit(rect)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ZoomableImageScrollArea(QScrollArea):
    image_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background-color: #121212;")
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #121212;")
        self.setWidget(self.image_label)
        
        self.grabGesture(Qt.PinchGesture)
        
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.is_fit = True
        self.gesture_start_zoom = 1.0
        
    def set_pixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.zoom_factor = 1.0
        self.is_fit = True
        self.setWidgetResizable(True)
        self.update_view()
        
    def update_view(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
            
        if self.is_fit:
            self.setWidgetResizable(True)
            viewport_size = self.viewport().size()
            scaled = self.original_pixmap.scaled(
                viewport_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.setWidgetResizable(False)
            w = int(self.original_pixmap.width() * self.zoom_factor)
            h = int(self.original_pixmap.height() * self.zoom_factor)
            scaled = self.original_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.resize(w, h)
            self.image_label.setPixmap(scaled)
        self.update_cursor()
            
    def event(self, event):
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)
        
    def gestureEvent(self, event):
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            self.pinchTriggered(pinch)
            event.accept(Qt.PinchGesture)
            return True
        return False
        
    def pinchTriggered(self, gesture):
        if gesture.state() == Qt.GestureStarted:
            if self.is_fit:
                if self.image_label.pixmap() and hasattr(self, 'original_pixmap') and self.original_pixmap and self.original_pixmap.width() > 0:
                    self.zoom_factor = self.image_label.pixmap().width() / self.original_pixmap.width()
                else:
                    self.zoom_factor = 1.0
                self.is_fit = False
            self.gesture_start_zoom = self.zoom_factor
                 
        factor = gesture.scaleFactor()
        self.zoom_factor = max(0.1, min(self.gesture_start_zoom * factor, 10.0))
        self.update_view()

    def update_cursor(self):
        if self.is_fit:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            if hasattr(self, 'is_dragging') and self.is_dragging:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)

    def enterEvent(self, event):
        self.update_cursor()
        super().enterEvent(event)

    def wheelEvent(self, event):
        if not self.original_pixmap or self.original_pixmap.isNull():
            super().wheelEvent(event)
            return
            
        viewport_pos = event.pos()
        widget_pos = self.widget().mapFrom(self.viewport(), viewport_pos)
        
        old_zoom = self.zoom_factor
        if self.is_fit:
            if self.image_label.pixmap() and hasattr(self, 'original_pixmap') and self.original_pixmap and self.original_pixmap.width() > 0:
                old_zoom = self.image_label.pixmap().width() / self.original_pixmap.width()
            else:
                old_zoom = 1.0
            self.is_fit = False
            
        angle = event.angleDelta().y()
        factor = 1.15 if angle > 0 else 0.85
        self.zoom_factor = max(0.1, min(old_zoom * factor, 10.0))
        
        if self.widget().rect().contains(widget_pos):
            zoom_center_viewport = viewport_pos
            zoom_center_widget = widget_pos
        else:
            zoom_center_viewport = QPoint(self.viewport().width() // 2, self.viewport().height() // 2)
            zoom_center_widget = self.widget().mapFrom(self.viewport(), zoom_center_viewport)
            
        self.update_view()
        
        if old_zoom > 0:
            zoom_ratio = self.zoom_factor / old_zoom
            new_x = zoom_center_widget.x() * zoom_ratio
            new_y = zoom_center_widget.y() * zoom_ratio
            self.horizontalScrollBar().setValue(int(new_x - zoom_center_viewport.x()))
            self.verticalScrollBar().setValue(int(new_y - zoom_center_viewport.y()))
            
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.is_fit = not self.is_fit
        if self.is_fit:
            self.zoom_factor = 1.0
        else:
            self.zoom_factor = 2.0
        self.update_view()
        event.accept()

    def resizeEvent(self, event):
        if self.is_fit:
            self.update_view()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.scroll_start_h = self.horizontalScrollBar().value()
            self.scroll_start_v = self.verticalScrollBar().value()
            self.is_dragging = True
            self.update_cursor()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'is_dragging') and self.is_dragging:
            delta = event.pos() - self.drag_start_pos
            self.horizontalScrollBar().setValue(self.scroll_start_h - delta.x())
            self.verticalScrollBar().setValue(self.scroll_start_v - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.update_cursor()
            if hasattr(self, 'drag_start_pos'):
                diff = (event.pos() - self.drag_start_pos).manhattanLength()
                if diff < 8:
                    self.image_clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class GridImageItem(QWidget):
    clicked = pyqtSignal(object)
    double_clicked = pyqtSignal(object)
    
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 220)
        
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        
        self.pixmap = QPixmap(filepath)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(self.image_label)
        
        self.update_image()
        
    def set_selected(self, selected):
        self.selected = selected
        self.update()
        
    def update_image(self):
        if not self.pixmap.isNull():
            w = max(10, self.width() - 10)
            h = max(10, self.height() - 10)
            scaled = self.pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.selected:
            painter.setPen(QPen(QColor("#38bdf8"), 3))
            painter.setBrush(QBrush(QColor(56, 189, 248, 20)))
        else:
            painter.setPen(QPen(QColor("#333333"), 1))
            painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
        painter.end()


class DetailViewer(QWidget):
    media_closed = pyqtSignal()
    image_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        # 1. Image View Setup
        self.image_scroll = ZoomableImageScrollArea()
        self.image_scroll.image_clicked.connect(self.image_clicked.emit)
        self.stacked_widget.addWidget(self.image_scroll)
        
        # 2. Video View Setup
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: #121212;")
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000;")
        video_layout.addWidget(self.video_widget)
        
        self.video_controls = QWidget()
        self.video_controls.setFixedHeight(50)
        self.video_controls.setStyleSheet("background-color: #1e1e1e; border-top: 1px solid #333;")
        controls_layout = QHBoxLayout(self.video_controls)
        controls_layout.setContentsMargins(15, 5, 15, 5)
        controls_layout.setSpacing(10)
        
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(40, 30)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #555;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """)
        self.play_button.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_button)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setRange(0, 0)
        self.video_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #262626;
                height: 6px;
                background: #333;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #e0e0e0;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
            }
        """)
        self.video_slider.sliderMoved.connect(self.set_video_position)
        controls_layout.addWidget(self.video_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #a0a0a0; font-size: 12px; font-family: monospace;")
        controls_layout.addWidget(self.time_label)
        
        self.mute_button = QPushButton("🔊")
        self.mute_button.setFixedSize(40, 30)
        self.mute_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        self.mute_button.clicked.connect(self.toggle_mute)
        controls_layout.addWidget(self.mute_button)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #333;
            }
            QSlider::sub-page:horizontal {
                background: #e0e0e0;
            }
            QSlider::handle:horizontal {
                background: #fff;
                width: 10px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 5px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.volume_slider)
        
        video_layout.addWidget(self.video_controls)
        self.stacked_widget.addWidget(self.video_container)
        
        # Initialize media player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self.video_position_changed)
        self.media_player.durationChanged.connect(self.video_duration_changed)
        self.media_player.stateChanged.connect(self.video_state_changed)
        
        # 3. PDF View Setup
        self.pdf_container = QWidget()
        self.pdf_container.setStyleSheet("background-color: #121212;")
        pdf_layout = QVBoxLayout(self.pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.setSpacing(0)
        
        self.pdf_controls = QWidget()
        self.pdf_controls.setFixedHeight(50)
        self.pdf_controls.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        pdf_ctrl_layout = QHBoxLayout(self.pdf_controls)
        pdf_ctrl_layout.setContentsMargins(15, 5, 15, 5)
        pdf_ctrl_layout.setSpacing(10)
        
        self.pdf_prev_btn = QPushButton("◀ Prev")
        self.pdf_prev_btn.setFixedSize(70, 30)
        self.pdf_prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #181818;
                color: #555;
                border-color: #2b2b2b;
            }
        """)
        self.pdf_prev_btn.clicked.connect(self.pdf_prev_page)
        pdf_ctrl_layout.addWidget(self.pdf_prev_btn)
        
        self.pdf_page_label = QLabel("Page 0 of 0")
        self.pdf_page_label.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: bold;")
        pdf_ctrl_layout.addWidget(self.pdf_page_label)
        
        self.pdf_next_btn = QPushButton("Next ▶")
        self.pdf_next_btn.setFixedSize(70, 30)
        self.pdf_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #181818;
                color: #555;
                border-color: #2b2b2b;
            }
        """)
        self.pdf_next_btn.clicked.connect(self.pdf_next_page)
        pdf_ctrl_layout.addWidget(self.pdf_next_btn)
        
        pdf_ctrl_layout.addStretch()
        
        self.pdf_zoom_out_btn = QPushButton("🔍-")
        self.pdf_zoom_out_btn.setFixedSize(40, 30)
        self.pdf_zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        self.pdf_zoom_out_btn.clicked.connect(self.pdf_zoom_out)
        pdf_ctrl_layout.addWidget(self.pdf_zoom_out_btn)
        
        self.pdf_zoom_label = QLabel("100%")
        self.pdf_zoom_label.setStyleSheet("color: #a0a0a0; font-size: 13px; min-width: 40px; qproperty-alignment: AlignCenter;")
        pdf_ctrl_layout.addWidget(self.pdf_zoom_label)
        
        self.pdf_zoom_in_btn = QPushButton("🔍+")
        self.pdf_zoom_in_btn.setFixedSize(40, 30)
        self.pdf_zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        self.pdf_zoom_in_btn.clicked.connect(self.pdf_zoom_in)
        pdf_ctrl_layout.addWidget(self.pdf_zoom_in_btn)
        
        pdf_layout.addWidget(self.pdf_controls)
        
        self.pdf_scroll = QScrollArea()
        self.pdf_scroll.setWidgetResizable(True)
        self.pdf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.pdf_scroll.setStyleSheet("background-color: #121212;")
        
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_label.setStyleSheet("background-color: #121212; padding: 10px;")
        self.pdf_scroll.setWidget(self.pdf_label)
        
        pdf_layout.addWidget(self.pdf_scroll)
        self.stacked_widget.addWidget(self.pdf_container)
        
        # 4. Placeholder View Setup
        self.placeholder_container = QWidget()
        self.placeholder_container.setStyleSheet("background-color: #121212;")
        placeholder_layout = QVBoxLayout(self.placeholder_container)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.placeholder_icon = QLabel("🖼️")
        self.placeholder_icon.setStyleSheet("font-size: 64px; margin-bottom: 20px;")
        self.placeholder_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_icon)
        
        self.placeholder_text = QLabel("Select a media file or drop multiple images here")
        self.placeholder_text.setStyleSheet("color: #666666; font-size: 16px; font-weight: 500;")
        self.placeholder_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_text)
        
        self.stacked_widget.addWidget(self.placeholder_container)
        
        # 5. Multi Image View Setup (Scrollable Grid)
        self.multi_image_scroll = QScrollArea()
        self.multi_image_scroll.setWidgetResizable(True)
        self.multi_image_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.multi_image_scroll.setStyleSheet("background-color: #121212;")
        self.multi_image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.multi_image_container = QWidget()
        self.multi_image_container.setStyleSheet("background-color: #121212;")
        self.multi_image_grid = QGridLayout(self.multi_image_container)
        self.multi_image_grid.setContentsMargins(15, 15, 15, 15)
        self.multi_image_grid.setSpacing(15)
        
        self.multi_image_scroll.setWidget(self.multi_image_container)
        self.stacked_widget.addWidget(self.multi_image_scroll)

        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Floating Close Button
        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(36, 36)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(80, 80, 80, 0.6);
                border-radius: 18px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(220, 50, 50, 0.95);
                color: white;
                border: 1px solid rgba(220, 50, 50, 0.95);
            }
        """)
        self.close_button.clicked.connect(self.clear_media)
        self.close_button.hide()
        
        # Fit to screen button overlay
        self.fit_button = QPushButton("Fit", self)
        self.fit_button.setFixedSize(60, 36)
        self.fit_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(43, 43, 43, 0.85);
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(58, 58, 58, 0.95);
            }
        """)
        self.fit_button.clicked.connect(self.fit_to_screen)
        self.fit_button.hide()

        self.current_filepath = None
        self.current_pixmap = None
        self.current_pdf_doc = None
        self.current_pdf_page = 0
        self.pdf_zoom = 1.2
        self.is_muted = False
        self.last_volume = 70
        self.grid_items = []
        
        # Start on the placeholder screen
        self.stacked_widget.setCurrentIndex(3)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
        
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            image_paths = []
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(IMAGE_EXTS):
                    image_paths.append(path)
            if image_paths:
                print(f"Debug: Number of dropped images: {len(image_paths)}")
                self.load_multiple_media_grid(image_paths)
                event.acceptProposedAction()

    def fit_to_screen(self):
        if self.stacked_widget.currentIndex() == 0:
            self.image_scroll.is_fit = True
            self.image_scroll.zoom_factor = 1.0
            self.image_scroll.update_view()

    def load_media(self, filepath):
        self.anim.stop()
        self.media_player.stop()
        
        if self.current_pdf_doc:
            self.current_pdf_doc.close()
            self.current_pdf_doc = None
            
        self.current_filepath = filepath
        self.current_pixmap = None
        
        lower_path = filepath.lower()
        
        if lower_path.endswith(IMAGE_EXTS):
            self.stacked_widget.setCurrentIndex(0)
            pixmap = QPixmap(filepath)
            self.current_pixmap = pixmap
            self.image_scroll.set_pixmap(pixmap)
            self.fit_button.show()
        elif lower_path.endswith(PDF_EXTS):
            self.stacked_widget.setCurrentIndex(2)
            self.fit_button.hide()
            try:
                self.current_pdf_doc = fitz.open(filepath)
                self.current_pdf_page = 0
                self.pdf_zoom = 1.2
                self.update_pdf_page()
            except Exception as e:
                print(f"Error opening PDF: {e}")
                self.pdf_label.setText(f"Failed to load PDF: {e}")
        elif lower_path.endswith(VIDEO_EXTS):
            self.stacked_widget.setCurrentIndex(1)
            self.fit_button.hide()
            self.play_button.setText("▶")
            self.time_label.setText("00:00 / 00:00")
            self.video_slider.setValue(0)
            
            media_content = QMediaContent(QUrl.fromLocalFile(filepath))
            self.media_player.setMedia(media_content)
            self.media_player.play()
            
        self.close_button.show()
        self.close_button.raise_()
        
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def load_focused_image(self, filepath):
        self.stacked_widget.setCurrentIndex(0)
        pixmap = QPixmap(filepath)
        self.current_pixmap = pixmap
        self.image_scroll.set_pixmap(pixmap)
        self.close_button.show()
        self.close_button.raise_()
        self.fit_button.show()
        self.fit_button.raise_()

    def load_multiple_media_grid(self, image_paths):
        self.anim.stop()
        self.media_player.stop()
        if self.current_pdf_doc:
            self.current_pdf_doc.close()
            self.current_pdf_doc = None
            
        self.current_filepath = None
        self.current_pixmap = None
        
        self.clear_grid_items()
        
        self.current_media_list = image_paths
        self.grid_items = []
        
        for path in image_paths:
            item = GridImageItem(path, self)
            item.clicked.connect(self.on_grid_item_clicked)
            item.double_clicked.connect(self.on_grid_item_double_clicked)
            self.grid_items.append(item)
            
        self.rebuild_multi_image_grid(force=True)
        
        self.stacked_widget.setCurrentIndex(4) # Multi-image grid page
        self.close_button.show()
        self.close_button.raise_()
        self.fit_button.hide()
        
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def on_grid_item_clicked(self, clicked_item):
        for item in self.grid_items:
            item.set_selected(item == clicked_item)

    def on_grid_item_double_clicked(self, clicked_item):
        self.load_focused_image(clicked_item.filepath)

    def clear_grid_items(self):
        if hasattr(self, 'grid_items'):
            for item in self.grid_items:
                self.multi_image_grid.removeWidget(item)
                item.setParent(None)
                item.deleteLater()
            self.grid_items = []

    def rebuild_multi_image_grid(self, force=False):
        if not hasattr(self, 'grid_items') or not self.grid_items:
            return
            
        width = self.multi_image_scroll.viewport().width()
        if width <= 100:
            width = self.width()
        if width <= 100:
            width = 800
            
        cols = max(1, width // 220)
        
        if not force and hasattr(self, 'current_grid_cols') and self.current_grid_cols == cols:
            return
            
        self.current_grid_cols = cols
        
        for item in self.grid_items:
            self.multi_image_grid.removeWidget(item)
            
        for idx, item in enumerate(self.grid_items):
            row = idx // cols
            col = idx % cols
            self.multi_image_grid.addWidget(item, row, col)

    def update_image(self):
        self.image_scroll.update_view()

    def clear_media(self):
        # Return to multi-image grid if focused viewer is closed and we have a grid loaded
        if self.stacked_widget.currentIndex() == 0 and hasattr(self, 'grid_items') and self.grid_items:
            self.stacked_widget.setCurrentIndex(4)
            self.fit_button.hide()
            self.close_button.show()
            self.close_button.raise_()
            return
            
        self.anim.stop()
        self.media_player.stop()
        
        if self.current_pdf_doc:
            self.current_pdf_doc.close()
            self.current_pdf_doc = None
            
        self.current_filepath = None
        self.current_pixmap = None
        self.image_scroll.set_pixmap(QPixmap())
        self.clear_grid_items()
        
        self.stacked_widget.setCurrentIndex(3)
        self.close_button.hide()
        self.fit_button.hide()
        self.media_closed.emit()

    def update_pdf_page(self):
        if not self.current_pdf_doc:
            return
            
        num_pages = len(self.current_pdf_doc)
        if num_pages == 0:
            self.pdf_page_label.setText("No pages")
            self.pdf_prev_btn.setEnabled(False)
            self.pdf_next_btn.setEnabled(False)
            return
            
        if self.current_pdf_page < 0:
            self.current_pdf_page = 0
        elif self.current_pdf_page >= num_pages:
            self.current_pdf_page = num_pages - 1
            
        self.pdf_page_label.setText(f"Page {self.current_pdf_page + 1} of {num_pages}")
        self.pdf_zoom_label.setText(f"{int(self.pdf_zoom * 100)}%")
        
        self.pdf_prev_btn.setEnabled(self.current_pdf_page > 0)
        self.pdf_next_btn.setEnabled(self.current_pdf_page < num_pages - 1)
        
        try:
            page = self.current_pdf_doc.load_page(self.current_pdf_page)
            mat = fitz.Matrix(self.pdf_zoom, self.pdf_zoom)
            pix = page.get_pixmap(matrix=mat)
            
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            pixmap = QPixmap.fromImage(qimg)
            self.pdf_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error rendering PDF page: {e}")
            self.pdf_label.setText(f"Error rendering page: {e}")

    def pdf_prev_page(self):
        if self.current_pdf_doc and self.current_pdf_page > 0:
            self.current_pdf_page -= 1
            self.update_pdf_page()
            
    def pdf_next_page(self):
        if self.current_pdf_doc and self.current_pdf_page < len(self.current_pdf_doc) - 1:
            self.current_pdf_page += 1
            self.update_pdf_page()
            
    def pdf_zoom_in(self):
        if self.current_pdf_doc and self.pdf_zoom < 4.0:
            self.pdf_zoom += 0.2
            self.update_pdf_page()
            
    def pdf_zoom_out(self):
        if self.current_pdf_doc and self.pdf_zoom > 0.4:
            self.pdf_zoom -= 0.2
            self.update_pdf_page()

    def toggle_play(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
            
    def toggle_mute(self):
        if self.is_muted:
            self.media_player.setMuted(False)
            self.mute_button.setText("🔊")
            self.volume_slider.setValue(self.last_volume)
            self.is_muted = False
        else:
            self.last_volume = self.volume_slider.value()
            self.media_player.setMuted(True)
            self.mute_button.setText("🔇")
            self.volume_slider.setValue(0)
            self.is_muted = True
            
    def set_volume(self, value):
        self.media_player.setVolume(value)
        if value > 0:
            self.mute_button.setText("🔊")
            self.is_muted = False
        else:
            self.mute_button.setText("🔇")
            self.is_muted = True
            
    def set_video_position(self, position):
        self.media_player.setPosition(position)
        
    def video_position_changed(self, position):
        if not self.video_slider.isSliderDown():
            self.video_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())
        
    def video_duration_changed(self, duration):
        self.video_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)
        
    def video_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.setText("❚❚")
        else:
            self.play_button.setText("▶")
            
    def update_time_label(self, position, duration):
        pos_sec = position // 1000
        pos_min = pos_sec // 60
        pos_sec = pos_sec % 60
        
        dur_sec = duration // 1000
        dur_min = dur_sec // 60
        dur_sec = dur_sec % 60
        
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def resizeEvent(self, event):
        if self.stacked_widget.currentIndex() == 0:
            self.update_image()
        elif self.stacked_widget.currentIndex() == 4:
            self.rebuild_multi_image_grid()
        super().resizeEvent(event)
        
        margin = 15
        self.close_button.move(margin, margin)
        self.close_button.raise_()
        
        self.fit_button.move(margin + 45, margin)
        self.fit_button.raise_()


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
        self.detail_viewer.media_player.stop()
        if self.detail_viewer.current_pdf_doc:
            self.detail_viewer.current_pdf_doc.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())