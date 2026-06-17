import os
import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QSplitter, QGraphicsOpacityEffect,
    QFrame, QMainWindow, QStackedWidget, QPushButton, QSlider,
    QPinchGesture
)
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QKeyEvent, QPainterPath,
    QLinearGradient, QPolygon, QImage
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, pyqtProperty, QPropertyAnimation, 
    QEasingCurve, QRect, QPoint, QUrl, QEvent
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import fitz


# Dark theme colors
BG_COLOR = QColor("#121212")
CARD_BG = QColor("#2b2b2b")
CARD_HOVER = QColor("#3a3a3a")
CARD_SELECTED = QColor("#4a4a4a")
TEXT_COLOR = "#e0e0e0"
SCROLLBAR_BG = "#1e1e1e"
SCROLLBAR_HANDLE = "#555555"

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg')
VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.webm')
PDF_EXTS = ('.pdf',)
ALL_EXTS = IMAGE_EXTS + VIDEO_EXTS + PDF_EXTS

class ImageWorker(QThread):
    thumbnail_ready = pyqtSignal(str, str, str, QPixmap)
    finished_loading = pyqtSignal()

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.running = True

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
        
        # Round clip path
        path = QPainterPath()
        path.addRoundedRect(0, 0, 80, 80, 8, 8)
        painter.setClipPath(path)
        
        # Draw background gradient (dark charcoal/blue)
        grad = QLinearGradient(0, 0, 80, 80)
        grad.setColorAt(0, QColor("#1e293b"))
        grad.setColorAt(1, QColor("#0f172a"))
        painter.fillRect(0, 0, 80, 80, QBrush(grad))
        
        # Draw play icon in center
        painter.setBrush(QBrush(QColor("#38bdf8"))) # Light blue color
        painter.setPen(Qt.PenStyle.NoPen)
        
        poly = QPolygon([
            QPoint(32, 28),
            QPoint(32, 52),
            QPoint(54, 40)
        ])
        painter.drawPolygon(poly)
        painter.end()
        return rounded

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
                
                lower_name = filename.lower()
                rounded = None
                
                if lower_name.endswith(IMAGE_EXTS):
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        rounded = self.create_rounded_thumbnail(pixmap)
                elif lower_name.endswith(PDF_EXTS):
                    try:
                        doc = fitz.open(filepath)
                        if len(doc) > 0:
                            page = doc.load_page(0)
                            # Render at a small size for thumbnail
                            pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
                            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                            pixmap = QPixmap.fromImage(qimg)
                            rounded = self.create_rounded_thumbnail(pixmap)
                    except Exception as e:
                        print(f"Error making PDF thumbnail: {e}")
                elif lower_name.endswith(VIDEO_EXTS):
                    rounded = self.create_video_placeholder()
                
                if rounded:
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


class ZoomableImageScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background-color: #121212;")
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #121212;")
        self.setWidget(self.image_label)
        
        # Grab pinch gesture for touchscreen zoom support
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
                if self.image_label.pixmap():
                    self.zoom_factor = self.image_label.pixmap().width() / self.original_pixmap.width()
                else:
                    self.zoom_factor = 1.0
                self.is_fit = False
            self.gesture_start_zoom = self.zoom_factor
                
        factor = gesture.scaleFactor()
        self.zoom_factor = max(0.1, min(self.gesture_start_zoom * factor, 5.0))
        self.update_view()

    def wheelEvent(self, event):
        # Allow trackpad/mouse pinch gesture emulation via Ctrl + Scroll Wheel
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.is_fit:
                if self.image_label.pixmap():
                    self.zoom_factor = self.image_label.pixmap().width() / self.original_pixmap.width()
                else:
                    self.zoom_factor = 1.0
                self.is_fit = False
                
            angle = event.angleDelta().y()
            factor = 1.1 if angle > 0 else 0.9
            self.zoom_factor = max(0.1, min(self.zoom_factor * factor, 5.0))
            self.update_view()
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Double click to reset / toggle fit mode
        self.is_fit = not self.is_fit
        if self.is_fit:
            self.zoom_factor = 1.0
        else:
            self.zoom_factor = 1.0
        self.update_view()
        event.accept()

    def resizeEvent(self, event):
        if self.is_fit:
            self.update_view()
        super().resizeEvent(event)


class DetailViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        # 1. Image View Setup
        self.image_scroll = ZoomableImageScrollArea()
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
        
        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self.current_filepath = None
        self.current_pixmap = None
        self.current_pdf_doc = None
        self.current_pdf_page = 0
        self.pdf_zoom = 1.2
        self.is_muted = False
        self.last_volume = 70

    def load_media(self, filepath):
        self.anim.stop()
        self.media_player.stop()
        
        if self.current_pdf_doc:
            self.current_pdf_doc.close()
            self.current_pdf_doc = None
            
        self.current_filepath = filepath
        self.current_pixmap = None
        
        lower_path = filepath.lower()
        
        if lower_path.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg')):
            self.stacked_widget.setCurrentIndex(0)
            pixmap = QPixmap(filepath)
            self.current_pixmap = pixmap
            self.image_scroll.set_pixmap(pixmap)
        elif lower_path.endswith(('.pdf',)):
            self.stacked_widget.setCurrentIndex(2)
            try:
                self.current_pdf_doc = fitz.open(filepath)
                self.current_pdf_page = 0
                self.pdf_zoom = 1.2
                self.update_pdf_page()
            except Exception as e:
                print(f"Error opening PDF: {e}")
                self.pdf_label.setText(f"Failed to load PDF: {e}")
        elif lower_path.endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
            self.stacked_widget.setCurrentIndex(1)
            self.play_button.setText("▶")
            self.time_label.setText("00:00 / 00:00")
            self.video_slider.setValue(0)
            
            media_content = QMediaContent(QUrl.fromLocalFile(filepath))
            self.media_player.setMedia(media_content)
            self.media_player.play()
            
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def update_image(self):
        self.image_scroll.update_view()

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
        self.detail_viewer.load_media(selected_card.filepath)

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