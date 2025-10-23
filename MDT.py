import sys
import subprocess
import threading
import time
import json
import logging
from pathlib import Path
import Quartz
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QSystemTrayIcon,
                             QMenu, QAction, QMessageBox, QCheckBox)
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QDrag, QColor, QIcon, QKeySequence
from PyQt5.uic import loadUi
import os
import hashlib
import re
import res_rc  # Import the generated resource file

# 导入 macOS 原生剪切板 API
try:
    from AppKit import NSPasteboard, NSStringPboardType, NSPasteboardTypeString
    NATIVE_CLIPBOARD_AVAILABLE = True
except ImportError:
    NATIVE_CLIPBOARD_AVAILABLE = False

# ==================== 配置和日志设置 ====================

# 配置文件路径
CONFIG_DIR = Path.home() / ".mdt"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "mdt.log"

# 确保配置目录存在
CONFIG_DIR.mkdir(exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 记录剪切板 API 可用性
if NATIVE_CLIPBOARD_AVAILABLE:
    logger.info("使用原生 macOS 剪切板 API (AppKit.NSPasteboard)")
else:
    logger.warning("AppKit 不可用，将使用 subprocess 方式访问剪切板")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ==================== 配置管理 ====================

class ConfigManager:
    """配置管理器"""

    DEFAULT_CONFIG = {
        "key_bindings": {
            "X1": "right",  # "left" or "right"
            "X2": "left"
        },
        "window_position": None,  # {"x": 100, "y": 100}
        "feed_watch_enabled": False
    }

    @staticmethod
    def load_config():
        """加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 迁移旧配置
                    if "feed_watch_enabled" not in config:
                        config["feed_watch_enabled"] = False
                    if "auto_start" in config: # 移除旧的自启动配置
                        del config["auto_start"]
                    logger.info("配置加载成功")
                    return config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")

        return ConfigManager.DEFAULT_CONFIG.copy()

    @staticmethod
    def save_config(config):
        """保存配置"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("配置保存成功")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

# ==================== Feed Watch 功能 ====================

class FeedWatchThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("Feed Watch 功能已启动")
        last_clipboard_hash = None
        last_processed_hash = None
        check_interval = 0.5

        while not self._stop_event.is_set():
            clipboard_content = self.read_clipboard()

            if clipboard_content and clipboard_content.strip():
                current_hash = self.get_content_hash(clipboard_content)

                if current_hash != last_clipboard_hash:
                    last_clipboard_hash = current_hash

                    if self.check_feed_format(clipboard_content):
                        if current_hash != last_processed_hash:
                            data_type = "新融合数据" if "新融合" in clipboard_content else "Feed数据"
                            logger.info(f"检测到{data_type} [{time.strftime('%H:%M:%S')}]")

                            result = self.parse_feed_data(clipboard_content)

                            if result:
                                if self.write_clipboard(result):
                                    last_processed_hash = self.get_content_hash(result)
                                    logger.info(f"处理完成: {result}")
                                    self.show_notification("Feed数据处理", "✅ 已处理并复制到剪切板")
                                else:
                                    logger.error("写入剪切板失败")
                                    self.show_notification("Feed数据处理", "❌ 写入失败", sound=False)
                            else:
                                logger.warning("未找到有效数据")

            time.sleep(check_interval)
        logger.info("Feed Watch 功能已停止")

    def read_clipboard(self):
        """读取剪切板内容 - 使用原生 macOS API"""
        try:
            if NATIVE_CLIPBOARD_AVAILABLE:
                # 使用原生 NSPasteboard API
                pasteboard = NSPasteboard.generalPasteboard()
                # 尝试读取字符串内容
                content = pasteboard.stringForType_(NSPasteboardTypeString)
                if content is None:
                    # 尝试旧版 API
                    content = pasteboard.stringForType_(NSStringPboardType)
                return content if content else None
            else:
                # 降级到 subprocess 方式
                return subprocess.run(['pbpaste'], capture_output=True, text=True, check=True).stdout
        except Exception as e:
            logger.debug(f"读取剪切板失败: {e}")
            return None

    def write_clipboard(self, text):
        """写入剪切板内容 - 使用原生 macOS API"""
        try:
            if NATIVE_CLIPBOARD_AVAILABLE:
                # 使用原生 NSPasteboard API
                pasteboard = NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                # 尝试使用新版 API
                success = pasteboard.setString_forType_(text, NSPasteboardTypeString)
                if not success:
                    # 尝试旧版 API
                    success = pasteboard.setString_forType_(text, NSStringPboardType)
                return success
            else:
                # 降级到 subprocess 方式
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
                return process.returncode == 0
        except Exception as e:
            logger.error(f"写入剪切板失败: {e}")
            return False

    def show_notification(self, title, message, sound=True):
        sound_option = 'sound name "Glass"' if sound else ''
        apple_script = f'''
        display notification "{message}" with title "{title}" {sound_option}
        '''
        try:
            subprocess.run(['osascript', '-e', apple_script], check=True, capture_output=True)
        except Exception:
            pass

    def check_feed_format(self, text):
        feed_keywords = ['Feed总时长', 'Feed总分发', 'Feed人均时长', 'Feed人均分发']
        fusion_keywords = ['新融合总时长', '新融合总分发', '新融合人均时长', '新融合人均分发']
        has_feed = any(keyword in text for keyword in feed_keywords)
        has_fusion = any(keyword in text for keyword in fusion_keywords)
        has_percentage = bool(re.search(r'-?\d+\.\d+%', text))
        return (has_feed or has_fusion) and has_percentage

    def parse_feed_data(self, text):
        is_fusion_format = '新融合' in text
        if is_fusion_format:
            target_metrics = [
                ('新融合总时长', '二跳总时长'),
                ('新融合总分发', '二跳总分发'),
                ('新融合人均时长', '二跳人均时长'),
                ('新融合人均分发', '二跳人均分发')
            ]
        else:
            target_metrics = [
                ('Feed总时长', 'Feed总时长'),
                ('Feed总分发', 'Feed总分发'),
                ('Feed人均时长', 'Feed人均时长'),
                ('Feed人均分发', 'Feed人均分发')
            ]
        results = []
        lines = text.strip().split('\n')
        for source_metric, display_metric in target_metrics:
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith(source_metric):
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        percentage_match = re.search(r'(-?\d+\.\d+)%', next_line)
                        if percentage_match:
                            percentage = percentage_match.group(1)
                            percentage_float = float(percentage)
                            if percentage_float >= 0:
                                results.append(f"{display_metric}+{percentage}%")
                            else:
                                results.append(f"{display_metric}{percentage}%")
                            break
                    break
                i += 1
        return '，'.join(results) if results else None

    def get_content_hash(self, content):
        if content is None:
            return None
        return hashlib.md5(content.encode('utf-8')).hexdigest()


# ==================== 鼠标监听 ====================

# Global variable for the run loop
run_loop = None

# Key bindings (button -> function)
key_bindings = {
    3: None,  # X1
    4: None,  # X2
}

# 视觉反馈信号（用于跨线程通知）
visual_feedback_signal = None

def mouse_callback(proxy, type_, event, refcon):
    """Mouse event callback function"""
    try:
        button = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)
        if button in key_bindings and type_ == Quartz.kCGEventOtherMouseDown:
            func = key_bindings[button]
            if func:
                func()
                # 触发视觉反馈
                if visual_feedback_signal:
                    visual_feedback_signal.triggered.emit(button)
    except Exception as e:
        logger.error(f"鼠标回调错误: {e}")
    return event

def start_mouse_listener():
    """Start the mouse listener"""
    global run_loop
    try:
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
            logger.error("无法创建事件监听，可能缺少辅助功能权限")
            return

        runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(run_loop, runLoopSource, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        logger.info("鼠标监听已启动")
        Quartz.CFRunLoopRun()
    except Exception as e:
        logger.error(f"启动监听失败: {e}")

# ==================== 可拖拽标签 ====================

class DraggableLabel(QLabel):
    def __init__(self, text, parent, original_pos, identity):
        super().__init__(text, parent)
        self.original_pos = original_pos
        self.identity = identity
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

        if x1_rect.contains(self.mapToParent(event.pos())):
            self.parent().set_binding("X1", self.identity)
        elif x2_rect.contains(self.mapToParent(event.pos())):
            self.parent().set_binding("X2", self.identity)

        self.reset_position()
        self.parent().X1.setStyleSheet(self.parent().x1_original_stylesheet)
        self.parent().X2.setStyleSheet(self.parent().x2_original_stylesheet)

    def reset_position(self):
        self.animation.setEndValue(self.original_pos)
        self.animation.start()

# ==================== 视觉反馈信号 ====================

class VisualFeedbackSignal(QObject):
    """用于跨线程发送视觉反馈信号"""
    triggered = pyqtSignal(int)

# ==================== 主应用 ====================

class MDTApp(QWidget):
    def __init__(self):
        super().__init__()
        loadUi(resource_path("MDT.ui"), self)

        # 加载配置
        self.config = ConfigManager.load_config()

        # 预编译 AppleScript（性能优化）
        self.compiled_left_script = None
        self.compiled_right_script = None
        self._compile_scripts()

        # 根据配置初始化按键绑定
        x1_binding = self.config["key_bindings"]["X1"]
        if x1_binding == "right":
            self.X1_func = self.switch_to_right_desktop
            self.X2_func = self.switch_to_left_desktop
        else:
            self.X1_func = self.switch_to_left_desktop
            self.X2_func = self.switch_to_right_desktop

        key_bindings[3] = self.X1_func
        key_bindings[4] = self.X2_func

        self.m_drag = False

        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.x1_original_stylesheet = self.X1.styleSheet()
        self.x2_original_stylesheet = self.X2.styleSheet()

        self.left_label = DraggableLabel("左桌面", self, self.Left.pos(), "left")
        self.left_label.setGeometry(self.Left.geometry())
        self.left_label.setStyleSheet(self.Left.styleSheet())
        self.left_label.setAlignment(Qt.AlignCenter)
        self.Left.hide()

        self.right_label = DraggableLabel("右桌面", self, self.Right.pos(), "right")
        self.right_label.setGeometry(self.Right.geometry())
        self.right_label.setStyleSheet(self.Right.styleSheet())
        self.right_label.setAlignment(Qt.AlignCenter)
        self.Right.hide()

        self.update_bindings()

        # 恢复窗口位置
        if self.config["window_position"]:
            pos = self.config["window_position"]
            self.move(pos["x"], pos["y"])

        # 设置快捷键 Cmd+H 隐藏窗口
        self.setup_shortcuts()

        # 设置视觉反馈
        global visual_feedback_signal
        self.feedback_signal = VisualFeedbackSignal()
        self.feedback_signal.triggered.connect(self.show_visual_feedback)
        visual_feedback_signal = self.feedback_signal

        # Feed Watch
        self.feed_watch_thread = None

        logger.info("MDT 应用已启动")

    def _compile_scripts(self):
        """预编译 AppleScript 以提升性能"""
        try:
            # 暂时不预编译，因为 osascript 更简单可靠
            # 如果需要更高性能，可以使用 NSAppleScript
            pass
        except Exception as e:
            logger.error(f"预编译脚本失败: {e}")

    def setup_shortcuts(self):
        """设置快捷键"""
        from PyQt5.QtWidgets import QShortcut

        # Cmd+H 隐藏窗口
        hide_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        hide_shortcut.activated.connect(self.hide)

        logger.info("快捷键已设置")

    def set_binding(self, target, source):
        """设置按键绑定"""
        if source == "left":
            if target == "X1":
                self.X1_func = self.switch_to_left_desktop
                self.X2_func = self.switch_to_right_desktop
                self.config["key_bindings"]["X1"] = "left"
                self.config["key_bindings"]["X2"] = "right"
            else:
                self.X2_func = self.switch_to_left_desktop
                self.X1_func = self.switch_to_right_desktop
                self.config["key_bindings"]["X1"] = "right"
                self.config["key_bindings"]["X2"] = "left"
        else:  # source == "right"
            if target == "X1":
                self.X1_func = self.switch_to_right_desktop
                self.X2_func = self.switch_to_left_desktop
                self.config["key_bindings"]["X1"] = "right"
                self.config["key_bindings"]["X2"] = "left"
            else:
                self.X2_func = self.switch_to_right_desktop
                self.X1_func = self.switch_to_left_desktop
                self.config["key_bindings"]["X1"] = "left"
                self.config["key_bindings"]["X2"] = "right"

        self.update_bindings()
        ConfigManager.save_config(self.config)

    def update_bindings(self):
        """更新按键绑定显示"""
        key_bindings[3] = self.X1_func
        key_bindings[4] = self.X2_func
        if self.X1_func == self.switch_to_right_desktop:
            self.X1.setText("X1：右桌面")
            self.X2.setText("X2：左桌面")
        else:
            self.X1.setText("X1：左桌面")
            self.X2.setText("X2：右桌面")

    def switch_to_left_desktop(self):
        """切换到左侧桌面"""
        script = '''
        tell application "System Events"
            key code 123 using control down
        end tell
        '''
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            logger.debug("切换到左侧桌面")
        except Exception as e:
            logger.error(f"切换桌面失败: {e}")

    def switch_to_right_desktop(self):
        """切换到右侧桌面"""
        script = '''
        tell application "System Events"
            key code 124 using control down
        end tell
        '''
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            logger.debug("切换到右侧桌面")
        except Exception as e:
            logger.error(f"切换桌面失败: {e}")

    def show_visual_feedback(self, button):
        """显示按键触发的视觉反馈"""
        try:
            # 根据按键闪烁对应的标签
            if button == 3:  # X1
                target_label = self.X1
            else:  # X2
                target_label = self.X2

            # 保存原始样式
            original_style = target_label.styleSheet()

            # 添加高亮效果
            target_label.setStyleSheet(original_style + "background-color: rgba(15, 128, 255, 150);")

            # 200ms 后恢复
            QTimer.singleShot(200, lambda: target_label.setStyleSheet(original_style))
        except Exception as e:
            logger.error(f"视觉反馈失败: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        # 修复：正确检查鼠标按键状态
        if event.buttons() & Qt.LeftButton and self.m_drag:
            self.move(event.globalPos() - self.m_DragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False

    def closeEvent(self, event):
        """关闭窗口时保存位置并隐藏"""
        # 保存窗口位置
        pos = self.pos()
        self.config["window_position"] = {"x": pos.x(), "y": pos.y()}
        ConfigManager.save_config(self.config)

        event.ignore()
        self.hide()
        logger.info("窗口已隐藏")

# ==================== 主程序入口 ====================

def show_permission_dialog():
    """显示权限提示对话框"""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("需要辅助功能权限")
    msg.setText("MDT 需要辅助功能权限才能监听鼠标按键。")
    msg.setInformativeText(
        "请按照以下步骤授予权限：\n\n"
        "1. 打开「系统设置」\n"
        "2. 进入「隐私与安全性」→「辅助功能」\n"
        "3. 点击左下角新增 MDT 软件\n"
        "4. 重启 MDT 应用"
    )
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed

    window = MDTApp()

    # Create Tray Icon
    tray_icon = QSystemTrayIcon(QIcon(resource_path("icon.icns")), parent=app)
    tray_icon.setToolTip("MDT - 鼠标桌面切换")

    # Create Menu for Tray Icon
    menu = QMenu()
    show_action = QAction("显示", parent=app)

    # Feed Watch 选项
    feed_watch_action = QAction("数据处理", parent=app)
    feed_watch_action.setCheckable(True)
    feed_watch_action.setChecked(window.config.get("feed_watch_enabled", False))

    def toggle_feed_watch(checked):
        window.config["feed_watch_enabled"] = checked
        ConfigManager.save_config(window.config)
        if checked:
            if not window.feed_watch_thread or not window.feed_watch_thread.is_alive():
                window.feed_watch_thread = FeedWatchThread()
                window.feed_watch_thread.start()
        else:
            if window.feed_watch_thread and window.feed_watch_thread.is_alive():
                window.feed_watch_thread.stop()
                window.feed_watch_thread = None

    feed_watch_action.triggered.connect(toggle_feed_watch)

    # 根据配置启动 Feed Watch
    if window.config.get("feed_watch_enabled", False):
        toggle_feed_watch(True)


    quit_action = QAction("退出", parent=app)

    show_action.triggered.connect(window.show)
    quit_action.triggered.connect(app.quit)

    menu.addAction(show_action)
    menu.addAction(feed_watch_action)
    menu.addSeparator()
    menu.addAction(quit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

    # 双击托盘图标显示/隐藏窗口
    def on_tray_icon_activated(reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if window.isVisible():
                window.hide()
            else:
                window.show()
                window.raise_()
                window.activateWindow()

    tray_icon.activated.connect(on_tray_icon_activated)

    # 启动鼠标监听线程
    listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    listener_thread.start()

    logger.info("MDT 启动完成")
    sys.exit(app.exec_())
