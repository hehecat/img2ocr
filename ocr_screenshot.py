import subprocess
import pytesseract
from PIL import Image
from pynput import keyboard
import tempfile
import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QWidget, QListWidget, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QMessageBox, QStyleFactory, QSystemTrayIcon, QMenu, QAction, QKeySequenceEdit)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QSettings, QPoint
from PyQt5.QtGui import QPalette, QColor, QIcon, QKeySequence
from datetime import datetime
import cv2
import numpy as np
from aip import AipOcr
import json
import os
from pathlib import Path

# 定义OCR完成信号
class OCRSignal(QObject):
    ocr_complete = pyqtSignal(str)

ocr_signal = OCRSignal()

# 定义全局变量
global hotkey, listener
hotkey = None
listener = None

# 主窗口类
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR 工具")
        self.setGeometry(100, 100, 600, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建文本编辑框用于显示OCR结果
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("OCR 结果将显示在这里")
        layout.addWidget(self.text_edit)

        # 创建按钮布局
        button_layout = QHBoxLayout()

        # 创建复制按钮
        self.copy_button = QPushButton("复制到剪贴板")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_button)

        # 创建文字识别按钮
        self.ocr_button = QPushButton("文字识别")
        self.ocr_button.clicked.connect(self.perform_ocr_from_screenshot)
        button_layout.addWidget(self.ocr_button)

        # 将按钮布局添加到主布局
        layout.addLayout(button_layout)

        # 创建快捷键设置
        shortcut_layout = QHBoxLayout()
        shortcut_layout.addWidget(QLabel("快捷键:"))
        self.shortcut_edit = QKeySequenceEdit()
        shortcut_layout.addWidget(self.shortcut_edit)
        self.save_shortcut_button = QPushButton("保存快捷键")
        self.save_shortcut_button.clicked.connect(self.save_shortcut)
        shortcut_layout.addWidget(self.save_shortcut_button)
        layout.addLayout(shortcut_layout)

        # 创建历史记录列表
        history_label = QLabel("历史记录:")
        layout.addWidget(history_label)
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.show_history_item)
        layout.addWidget(self.history_list)

        # 创建百度OCR选项
        baidu_layout = QVBoxLayout()
        self.use_baidu_ocr = QCheckBox("使用百度OCR")
        baidu_layout.addWidget(self.use_baidu_ocr)

        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        api_key_layout.addWidget(self.api_key_input)
        baidu_layout.addLayout(api_key_layout)

        secret_key_layout = QHBoxLayout()
        secret_key_layout.addWidget(QLabel("Secret Key:"))
        self.secret_key_input = QLineEdit()
        secret_key_layout.addWidget(self.secret_key_input)
        baidu_layout.addLayout(secret_key_layout)

        # 添加保存按钮
        self.save_keys_button = QPushButton("保存密钥")
        self.save_keys_button.clicked.connect(self.save_api_keys)
        baidu_layout.addWidget(self.save_keys_button)

        # 添加显示保存位置的标签
        self.save_location_label = QLabel()
        baidu_layout.addWidget(self.save_location_label)

        layout.addLayout(baidu_layout)

        # 连接OCR完成信号到更新文本方法
        ocr_signal.ocr_complete.connect(self.update_text)

        # 历史记录列表
        self.history = []

        # 设置保存路径并加载保存的API密钥
        self.set_save_path()
        self.load_api_keys()

        # 应用自定义样式
        self.apply_custom_style()

        # 创建系统托盘图标
        self.create_tray_icon()

        # 加载保存的快捷键
        self.load_shortcut()

    def apply_custom_style(self):
        self.setStyle(QStyleFactory.create("Fusion"))  # 使用 Fusion 样式作为基础
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
        palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Highlight, QColor(76, 163, 224))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f0f0f0;
            }
            QTextEdit, QListWidget, QLineEdit {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLabel {
                color: #333333;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                height: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

    def create_tray_icon(self):
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # 请替换为您的图标文件

        # 创建托盘菜单
        tray_menu = QMenu()
        show_action = QAction("显示", self)
        quit_action = QAction("退出", self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        # 连接动作信号
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.instance().quit)

        # 设置托盘图标的菜单
        self.tray_icon.setContextMenu(tray_menu)

        # 显示托盘图标
        self.tray_icon.show()

        # 连接托盘图标的激活信号（双击）
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "OCR 工具",
            "应用程序已最小化到系统托盘",
            QSystemTrayIcon.Information,
            2000
        )

    def update_text(self, text):
        self.text_edit.setText(text)
        self.add_to_history(text)
        self.show()
        self.raise_()
        self.activateWindow()

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "复制成功", "文本已复制到剪贴板")

    def add_to_history(self, text):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        first_line = text.split('\n')[0].strip()
        preview = first_line[:40] + "..." if len(first_line) > 40 else first_line
        preview = preview.replace('\n', ' ')
        
        history_item = f"{timestamp} - {preview}"
        self.history.append((history_item, text))
        self.history_list.addItem(history_item)

    def show_history_item(self, item):
        index = self.history_list.row(item)
        _, full_text = self.history[index]
        self.text_edit.setText(full_text)

    def set_save_path(self):
        self.save_dir = Path.home() / ".config" / "screenshot_ocr"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.save_file = self.save_dir / "api_keys.json"
        self.save_location_label.setText(f"密钥保存位置: {self.save_file}")

    def save_api_keys(self):
        api_key = self.api_key_input.text()
        secret_key = self.secret_key_input.text()
        
        data = {
            "api_key": api_key,
            "secret_key": secret_key
        }
        
        with open(self.save_file, "w") as f:
            json.dump(data, f)
        
        QMessageBox.information(self, "保存成功", f"API密钥已保存到:\n{self.save_file}")

    def load_api_keys(self):
        if self.save_file.exists():
            with open(self.save_file, "r") as f:
                data = json.load(f)
            
            self.api_key_input.setText(data.get("api_key", ""))
            self.secret_key_input.setText(data.get("secret_key", ""))

    def save_shortcut(self):
        new_shortcut = self.shortcut_edit.keySequence().toString()
        settings = QSettings("YourCompany", "OCR Tool")
        settings.setValue("shortcut", new_shortcut)
        QMessageBox.information(self, "保存成功", f"新的快捷键 {new_shortcut} 已保存")
        self.update_global_hotkey(new_shortcut)

    def load_shortcut(self):
        settings = QSettings("YourCompany", "OCR Tool")
        saved_shortcut = settings.value("shortcut", "Ctrl+Alt+O")
        self.shortcut_edit.setKeySequence(QKeySequence(saved_shortcut))
        self.update_global_hotkey(saved_shortcut)

    def update_global_hotkey(self, shortcut):
        global hotkey, listener
        if listener:
            listener.stop()
        
        # 将 Qt 快捷键格式转换为 pynput 格式
        pynput_shortcut = self.qt_to_pynput_shortcut(shortcut)
        
        try:
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(pynput_shortcut),
                on_activate)
            listener = keyboard.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release))
            listener.start()
        except ValueError as e:
            QMessageBox.warning(self, "快捷键设置失败", f"无法设置快捷键: {str(e)}")

    def qt_to_pynput_shortcut(self, qt_shortcut):
        # 将 Qt 快捷键格式转换为 pynput 格式
        mapping = {
            'Ctrl': '<ctrl>',
            'Alt': '<alt>',
            'Shift': '<shift>',
            'Meta': '<cmd>',
        }
        parts = qt_shortcut.split('+')
        pynput_parts = [mapping.get(part, part.lower()) for part in parts]
        return '+'.join(pynput_parts)

    def perform_ocr_from_screenshot(self):
        img_path = take_screenshot()
        if img_path:
            perform_ocr(img_path)
            os.unlink(img_path)  # OCR完成后删除临时文件
        else:
            print("OCR操作已取消")

# 截图函数
def take_screenshot():
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        screenshot_path = temp_file.name
    
    # 使用maim进行区域选择截图
    result = subprocess.run(["maim", "-s", screenshot_path], capture_output=True)
    
    # 检查是否成功截图
    if result.returncode != 0:
        print("截图被取消或发生错误")
        os.unlink(screenshot_path)
        return None
    
    return screenshot_path

# 图像预处理函数
def preprocess_image(image_path):
    try:
        # 读取图像
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("无法读取图像文件")
        
        # 增强对比度（使用固定参数）
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl,a,b))
        contrasted = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        
        return contrasted
    except Exception as e:
        print(f"图像预处理过程中出错: {str(e)}")
        return None

# 百度OCR函数
def baidu_ocr(image_path, api_key, secret_key):
    APP_ID = '你的APP_ID'  # 请替换为你的APP_ID
    client = AipOcr(APP_ID, api_key, secret_key)

    with open(image_path, 'rb') as fp:
        image = fp.read()

    options = {}
    options["language_type"] = "CHN_ENG"
    options["detect_direction"] = "true"
    options["detect_language"] = "true"
    options["probability"] = "true"

    result = client.basicGeneral(image, options)
    
    if 'words_result' in result:
        return '\n'.join([item['words'] for item in result['words_result']])
    else:
        return "百度OCR未能识别出文字"

# OCR函数
def perform_ocr(image_path):
    try:
        processed_image = preprocess_image(image_path)
        if processed_image is None:
            ocr_signal.ocr_complete.emit("图像预处理失败，无法执行OCR")
            return
        
        cv2.imwrite(image_path, processed_image)  # 保存预处理后的图像

        if window.use_baidu_ocr.isChecked():
            api_key = window.api_key_input.text()
            secret_key = window.secret_key_input.text()
            if not api_key or not secret_key:
                ocr_signal.ocr_complete.emit("请输入有效的百度OCR API Key和Secret Key")
                return
            text = baidu_ocr(image_path, api_key, secret_key)
        else:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        
        if text.strip():
            ocr_signal.ocr_complete.emit(text.strip())
        else:
            ocr_signal.ocr_complete.emit("未能识别出任何文字。")
        
    except Exception as e:
        error_message = f"OCR处理过程中出错: {str(e)}"
        print(error_message)
        ocr_signal.ocr_complete.emit(error_message)

# 快捷键触发函数
def on_activate():
    if window:
        window.perform_ocr_from_screenshot()

# 用于处理键盘监听器的辅助函数
def for_canonical(f):
    return lambda k: f(listener.canonical(k))

# 创建应用和主窗口
app = QApplication(sys.argv)

# 设置应用程序范围的调色板
palette = QPalette()
palette.setColor(QPalette.Window, QColor(240, 240, 240))
palette.setColor(QPalette.WindowText, QColor(51, 51, 51))
palette.setColor(QPalette.Base, QColor(255, 255, 255))
palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
palette.setColor(QPalette.ToolTipText, QColor(51, 51, 51))
palette.setColor(QPalette.Text, QColor(51, 51, 51))
palette.setColor(QPalette.Button, QColor(240, 240, 240))
palette.setColor(QPalette.ButtonText, QColor(51, 51, 51))
palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
app.setPalette(palette)

window = MainWindow()
window.show()

sys.exit(app.exec_())