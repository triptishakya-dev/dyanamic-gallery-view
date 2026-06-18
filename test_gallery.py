import sys
import os
import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QRect, QPoint, QMimeData, QUrl
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from unittest.mock import MagicMock

# Import components
import gallery
gallery.QThread.start = MagicMock()

from gallery import MainWindow, ImageCard, GridImageItem, ZoomableImageScrollArea, DetailViewer

# Create QApplication instance for tests
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

class TestGalleryApp(unittest.TestCase):
    def setUp(self):
        # Create a temporary image file for testing
        self.test_img_path = os.path.abspath("test_image.png")
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.GlobalColor.red)
        pixmap.save(self.test_img_path)
        
        # Mock actual start calls to prevent real thread execution
        self.window = MainWindow()
        
    def tearDown(self):
        self.window.close()
        if os.path.exists(self.test_img_path):
            os.remove(self.test_img_path)
            
    def test_multi_selection(self):
        # Store original method
        orig_modifiers = QApplication.keyboardModifiers
        
        try:
            # Add dummy cards
            card1 = ImageCard(self.test_img_path, "test1.png", "2026-06-18 12:00", self.window)
            card2 = ImageCard(self.test_img_path, "test2.png", "2026-06-18 12:00", self.window)
            self.window.cards = [card1, card2]
            
            # Test default single selection
            QApplication.keyboardModifiers = MagicMock(return_value=Qt.KeyboardModifier.NoModifier)
            self.window.on_card_clicked(card1.filepath, card1)
            self.assertTrue(card1.selected)
            self.assertFalse(card2.selected)
            
            # Test Ctrl+Click on card2
            QApplication.keyboardModifiers = MagicMock(return_value=Qt.KeyboardModifier.ControlModifier)
            self.window.on_card_clicked(card2.filepath, card2)
            self.assertTrue(card1.selected)
            self.assertTrue(card2.selected)
            
            # Test Ctrl+Click on card1
            self.window.on_card_clicked(card1.filepath, card1)
            self.assertFalse(card1.selected)
            self.assertTrue(card2.selected)
            
            # Reset modifiers mock
            QApplication.keyboardModifiers = MagicMock(return_value=Qt.KeyboardModifier.NoModifier)
            
            # Test rubber band drag selection
            card1.setGeometry(0, 0, 280, 100)
            card2.setGeometry(0, 110, 280, 100)
            
            # Box covering card1
            rect = QRect(0, 0, 280, 50)
            self.window.on_selection_box_changed(rect)
            self.assertTrue(card1.selected)
            self.assertFalse(card2.selected)
        finally:
            # Restore original method
            QApplication.keyboardModifiers = orig_modifiers

    def test_drag_and_drop(self):
        viewer = self.window.detail_viewer
        
        mime_data = QMimeData()
        mime_data.setUrls([
            QUrl.fromLocalFile(self.test_img_path),
            QUrl.fromLocalFile(self.test_img_path)
        ])
        
        # Construct a drag enter event
        drag_enter_ev = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        viewer.dragEnterEvent(drag_enter_ev)
        self.assertTrue(drag_enter_ev.isAccepted())
        
        # Construct a drop event
        drop_ev = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        viewer.dropEvent(drop_ev)
        
        # Check grid items
        self.assertEqual(len(viewer.grid_items), 2)
        self.assertEqual(viewer.grid_items[0].filepath, self.test_img_path)
        self.assertEqual(viewer.grid_items[1].filepath, self.test_img_path)
        self.assertEqual(viewer.stacked_widget.currentIndex(), 4)

    def test_grid_rendering(self):
        viewer = self.window.detail_viewer
        viewer.load_multiple_media_grid([self.test_img_path, self.test_img_path])
        self.assertEqual(len(viewer.grid_items), 2)
        
        item1 = viewer.grid_items[0]
        item2 = viewer.grid_items[1]
        
        viewer.on_grid_item_clicked(item1)
        self.assertTrue(item1.selected)
        self.assertFalse(item2.selected)
        
        viewer.multi_image_scroll.viewport().resize(500, 500)
        viewer.rebuild_multi_image_grid(force=True)
        self.assertEqual(viewer.current_grid_cols, 2)

    def test_start_drag_operations(self):
        from unittest.mock import patch
        
        card1 = ImageCard(self.test_img_path, "test1.png", "2026-06-18 12:00", self.window)
        card2 = ImageCard(self.test_img_path, "test2.png", "2026-06-18 12:00", self.window)
        self.window.cards = [card1, card2]
        
        card1.set_selected(True)
        card2.set_selected(True)
        
        with patch('gallery.QDrag.exec_', return_value=Qt.DropAction.CopyAction) as mock_exec, \
             patch('gallery.QDrag.setMimeData') as mock_set_mime:
             
            self.window.start_drag_operations(card1)
            
            mock_set_mime.assert_called_once()
            mime_data = mock_set_mime.call_args[0][0]
            self.assertTrue(mime_data.hasUrls())
            self.assertEqual(len(mime_data.urls()), 2)

    def test_image_zoom(self):
        zoom_area = ZoomableImageScrollArea()
        pix = QPixmap(self.test_img_path)
        zoom_area.set_pixmap(pix)
        
        self.assertTrue(zoom_area.is_fit)
        self.assertEqual(zoom_area.zoom_factor, 1.0)
        
        # Double click to zoom
        class DummyEvent:
            def accept(self): pass
        zoom_area.mouseDoubleClickEvent(DummyEvent())
        self.assertFalse(zoom_area.is_fit)
        self.assertEqual(zoom_area.zoom_factor, 2.0)
        
        # Fit to screen option test
        self.window.detail_viewer.stacked_widget.setCurrentIndex(0)
        self.window.detail_viewer.image_scroll.set_pixmap(pix)
        self.window.detail_viewer.image_scroll.is_fit = False
        self.window.detail_viewer.fit_to_screen()
        self.assertTrue(self.window.detail_viewer.image_scroll.is_fit)
        
    def test_focused_viewer_open_close(self):
        viewer = self.window.detail_viewer
        viewer.load_multiple_media_grid([self.test_img_path, self.test_img_path])
        
        item = viewer.grid_items[0]
        viewer.on_grid_item_double_clicked(item)
        
        self.assertEqual(viewer.stacked_widget.currentIndex(), 0)
        
        viewer.clear_media()
        self.assertEqual(viewer.stacked_widget.currentIndex(), 4)
        
        viewer.clear_media()
        self.assertEqual(viewer.stacked_widget.currentIndex(), 3)

    def test_dynamic_layout_and_features(self):
        viewer = self.window.detail_viewer
        
        # 1. Load single image
        viewer.load_multiple_media_grid([self.test_img_path])
        self.assertEqual(len(viewer.grid_items), 1)
        self.assertEqual(viewer.current_grid_cols, 1)
        self.assertEqual(viewer.badge_label.text(), "📁 1 Image")
        self.assertFalse(viewer.badge_label.isHidden())
        
        # 2. Append another image (simulate drag & drop append)
        viewer.load_multiple_media_grid([self.test_img_path], append=True)
        self.assertEqual(len(viewer.grid_items), 2)
        self.assertEqual(viewer.current_grid_cols, 2)
        self.assertEqual(viewer.badge_label.text(), "📁 2 Images")
        
        # 3. Test remove item request
        item_to_remove = viewer.grid_items[0]
        viewer.on_remove_item_requested(item_to_remove)
        self.assertEqual(len(viewer.grid_items), 1)
        self.assertEqual(viewer.current_grid_cols, 1)
        self.assertEqual(viewer.badge_label.text(), "📁 1 Image")

if __name__ == '__main__':
    unittest.main()
