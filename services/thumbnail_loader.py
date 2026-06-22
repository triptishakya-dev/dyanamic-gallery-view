from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QWaitCondition, QRect, QPoint
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPainterPath, QPen, QBrush, QColor, QLinearGradient, QPolygon
import fitz
from config.constants import IMAGE_EXTS, VIDEO_EXTS, PDF_EXTS

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
        return self.create_document_placeholder()

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

    def create_document_placeholder(self):
        rounded = QPixmap(80, 80)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, 80, 80, 8, 8)
        painter.setClipPath(path)

        grad = QLinearGradient(0, 0, 80, 80)
        grad.setColorAt(0, QColor("#334155"))
        grad.setColorAt(1, QColor("#1e293b"))
        painter.fillRect(0, 0, 80, 80, QBrush(grad))

        painter.setBrush(QBrush(QColor("#94a3b8")))
        painter.setPen(Qt.PenStyle.NoPen)

        # Draw a simple document icon
        painter.drawRect(25, 20, 30, 40)
        painter.setBrush(QBrush(QColor("#1e293b")))
        painter.drawRect(30, 28, 15, 2)
        painter.drawRect(30, 36, 20, 2)
        painter.drawRect(30, 44, 20, 2)
        
        painter.end()
        return rounded
