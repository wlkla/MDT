import sys
import subprocess
import threading
import time
import Quartz
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QMimeData
from PyQt5.QtGui import QDrag, QColor, QIcon
from PyQt5.uic import loadUi
import os
import res_rc  # Import the generated resource file

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Global variable for the run loop
run_loop = None

# Key bindings (button -> function)
key_bindings = {
    3: None,  # X1
    4: None,  # X2
}

def mouse_callback(proxy, type_, event, refcon):
    """Mouse event callback function"""
    try:
        button = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)
        if button in key_bindings and type_ == Quartz.kCGEventOtherMouseDown:
            func = key_bindings[button]
            if func:
                print(f"Calling function for button {button}")
                func()
    except Exception as e:
        print(f"Mouse callback error: {e}")
    return event

def start_mouse_listener():
    """Start the mouse listener"""
    global run_loop
    try:
        print("Starting mouse listener...")
        event_mask = (1 << Quartz.kCGEventOtherMouseDown)
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGHIDEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            mouse_callback,
            None,
        )

        if not tap:
            print("Failed to create event tap, accessibility permission may be required.")
            return

        runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(run_loop, runLoopSource, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        print("Mouse listener started.")
        Quartz.CFRunLoopRun()
    except Exception as e:
        print(f"Failed to start listener: {e}")

class DraggableLabel(QLabel):
    def __init__(self, text, parent, original_pos):
        super().__init__(text, parent)
        self.original_pos = original_pos
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            self.dragging = True

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return

        self.move(self.mapToParent(event.pos() - self.drag_start_position))

        x1_rect = self.parent().X1.geometry()
        x2_rect = self.parent().X2.geometry()

        if x1_rect.contains(self.mapToParent(event.pos())):
            self.parent().X1.setStyleSheet(self.parent().x1_original_stylesheet + "color: gray;")
        else:
            self.parent().X1.setStyleSheet(self.parent().x1_original_stylesheet)

        if x2_rect.contains(self.mapToParent(event.pos())):
            self.parent().X2.setStyleSheet(self.parent().x2_original_stylesheet + "color: gray;")
        else:
            self.parent().X2.setStyleSheet(self.parent().x2_original_stylesheet)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        x1_rect = self.parent().X1.geometry()
        x2_rect = self.parent().X2.geometry()

        if x1_rect.contains(self.mapToParent(event.pos())) or x2_rect.contains(self.mapToParent(event.pos())):
            self.parent().swap_functions()

        self.reset_position()
        self.parent().X1.setStyleSheet(self.parent().x1_original_stylesheet)
        self.parent().X2.setStyleSheet(self.parent().x2_original_stylesheet)

    def reset_position(self):
        self.animation.setEndValue(self.original_pos)
        self.animation.start()

class MDTApp(QWidget):
    def __init__(self):
        super().__init__()
        loadUi(resource_path("MDT.ui"), self)

        self.X1_func = self.switch_to_right_desktop
        self.X2_func = self.switch_to_left_desktop
        key_bindings[3] = self.X1_func
        key_bindings[4] = self.X2_func

        self.m_drag = False

        #self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        #self.setAttribute(Qt.WA_TranslucentBackground)

        self.x1_original_stylesheet = self.X1.styleSheet()
        self.x2_original_stylesheet = self.X2.styleSheet()

        self.left_label = DraggableLabel("左桌面", self, self.Left.pos())
        self.left_label.setGeometry(self.Left.geometry())
        self.left_label.setStyleSheet(self.Left.styleSheet())
        self.left_label.setAlignment(Qt.AlignCenter)
        self.Left.hide()

        self.right_label = DraggableLabel("右桌面", self, self.Right.pos())
        self.right_label.setGeometry(self.Right.geometry())
        self.right_label.setStyleSheet(self.Right.styleSheet())
        self.right_label.setAlignment(Qt.AlignCenter)
        self.Right.hide()

    def swap_functions(self):
        print("Swapping functions")
        self.X1_func, self.X2_func = self.X2_func, self.X1_func
        key_bindings[3] = self.X1_func
        key_bindings[4] = self.X2_func
        if self.X1_func == self.switch_to_right_desktop:
            self.X1.setText("X1：右桌面")
            self.X2.setText("X2：左桌面")
        else:
            self.X1.setText("X1：左桌面")
            self.X2.setText("X2：右桌面")
        print(f"X1 is now: {self.X1.text()}")
        print(f"X2 is now: {self.X2.text()}")

    def switch_to_left_desktop(self):
        print("Attempting to switch to left desktop")
        script = '''
        tell application "System Events"
            key code 123 using control down
        end tell
        '''
        subprocess.run(["osascript", "-e", script])

    def switch_to_right_desktop(self):
        print("Attempting to switch to right desktop")
        script = '''
        tell application "System Events"
            key code 124 using control down
        end tell
        '''
        subprocess.run(["osascript", "-e", script])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if Qt.LeftButton and self.m_drag:
            self.move(event.globalPos() - self.m_DragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False

    def closeEvent(self, event):
        event.ignore()
        self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed

    window = MDTApp()

    # Create Tray Icon
    tray_icon = QSystemTrayIcon(QIcon(resource_path("icon.icns")), parent=app)
    tray_icon.setToolTip("MDT")

    # Create Menu for Tray Icon
    menu = QMenu()
    show_action = QAction("显示", parent=app)
    quit_action = QAction("退出", parent=app)

    show_action.triggered.connect(window.show)
    quit_action.triggered.connect(app.quit)

    menu.addAction(show_action)
    menu.addAction(quit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

    listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    listener_thread.start()

    sys.exit(app.exec_())
