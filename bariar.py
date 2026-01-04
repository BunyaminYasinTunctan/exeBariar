import sys
import psutil
import json
import os
import random
import string
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QLineEdit, QMessageBox, QLabel, QInputDialog, QComboBox, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QAction, QIcon

class AppWaitThread(QThread):
    finished_signal = pyqtSignal()
    def __init__(self, process):
        super().__init__()
        self.process = process
    def run(self):
        self.process.wait()
        self.finished_signal.emit()

class MonitoringThread(QThread):
    password_required_signal = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.target_application_path = ""
        self.is_running = True
        self.is_authorized = False 
    def run(self):
        while self.is_running:
            if self.target_application_path and not self.is_authorized:
                for proc in psutil.process_iter(['exe']):
                    try:
                        if proc.info['exe'] and os.path.normpath(proc.info['exe']).lower() == os.path.normpath(self.target_application_path).lower():
                            proc.kill()
                            self.password_required_signal.emit()
                    except (psutil.NoSuchProcess, psutil.AccessDenied): continue
            self.msleep(500)

class UnlockWindow(QWidget):
    authenticated_signal = pyqtSignal()
    def __init__(self, correct_password, recovery_key, lang_data):
        super().__init__()
        self.correct_password = correct_password
        self.recovery_key = recovery_key
        self.lang = lang_data
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(350, 200)
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel(self.lang["access_locked"])
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_field)
        self.unlock_btn = QPushButton(self.lang["unlock"])
        self.unlock_btn.clicked.connect(self.check_password)
        layout.addWidget(self.unlock_btn)
        self.forgot_btn = QPushButton(self.lang["forgot"])
        self.forgot_btn.setStyleSheet("color: grey; border: none; font-size: 10px;")
        self.forgot_btn.clicked.connect(self.use_recovery_key)
        layout.addWidget(self.forgot_btn)
        self.setLayout(layout)
    def check_password(self):
        if self.password_field.text() == self.correct_password:
            self.authenticated_signal.emit()
            self.close()
        else: QMessageBox.critical(self, "!", self.lang["wrong_pass"])
    def use_recovery_key(self):
        key, ok = QInputDialog.getText(self, self.lang["recovery"], self.lang["enter_key"])
        if ok and key == self.recovery_key:
            self.authenticated_signal.emit()
            self.close()

class AppLocker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_file = "config.json"
        self.target_application_path = ""
        self.encrypted_password = ""
        self.recovery_key = ""
        self.current_lang = "TR"
        
        self.translations = {
            "TR": {"title": "Exe Bariar", "select": "EXE Seç", "pass_placeholder": "Şifre", "save": "Kaydet ve Gizle", "access_locked": "<b>KİLİTLİ</b>", "unlock": "Aç", "forgot": "Unuttum", "wrong_pass": "Hatalı!", "recovery": "Kurtarma", "enter_key": "Anahtar:", "credit": "Yapımcı: Bünyamin Yasn Tunçtan"},
            "EN": {"title": "Exe Bariar", "select": "Select EXE", "pass_placeholder": "Password", "save": "Save and Hide", "access_locked": "<b>LOCKED</b>", "unlock": "Unlock", "forgot": "Forgot", "wrong_pass": "Wrong!", "recovery": "Recovery", "enter_key": "Key:", "credit": "By: Bünyamin Yasn Tunçtan"}
        }

        self.process_monitor_thread = MonitoringThread()
        self.process_monitor_thread.password_required_signal.connect(self.show_unlock_screen)
        self.process_monitor_thread.start()
        
        self.init_ui()
        self.setup_tray()
        self.load_settings()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        
        menu = QMenu()
        show_action = QAction("Yönetim Paneli", self)
        show_action.triggered.connect(self.showNormal)
        exit_action = QAction("Tamamen Kapat (Çıkış)", self)
        exit_action.triggered.connect(self.force_quit)
        
        menu.addAction(show_action)
        menu.addAction(exit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def init_ui(self):
        self.main_window = QWidget()
        self.setCentralWidget(self.main_window)
        layout = QVBoxLayout()
        self.lang_box = QComboBox()
        self.lang_box.addItems(["TR", "EN"])
        self.lang_box.currentTextChanged.connect(self.change_language)
        layout.addWidget(self.lang_box)
        self.app_selector_btn = QPushButton()
        self.app_selector_btn.clicked.connect(self.select_application)
        layout.addWidget(self.app_selector_btn)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)
        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)
        self.credit_label = QLabel()
        self.credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.credit_label)
        self.main_window.setLayout(layout)
        self.update_ui_text()

    def change_language(self, lang):
        self.current_lang = lang
        self.update_ui_text()

    def update_ui_text(self):
        t = self.translations[self.current_lang]
        self.setWindowTitle(t["title"])
        self.app_selector_btn.setText(t["select"])
        self.password_input.setPlaceholderText(t["pass_placeholder"])
        self.save_btn.setText(t["save"])
        self.credit_label.setText(t["credit"])

    def select_application(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "EXE", "C:\\", "*.exe")
        if path: self.target_application_path = path

    def save_settings(self):
        password = self.password_input.text()
        if len(password) >= 12:
            self.encrypted_password = password
            if not self.recovery_key:
                self.recovery_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            data = {"path": self.target_application_path, "pass": self.encrypted_password, "recovery": self.recovery_key, "lang": self.current_lang}
            with open(self.config_file, "w") as f: json.dump(data, f)
            self.process_monitor_thread.target_application_path = self.target_application_path
            QMessageBox.information(self, "Key", f"Recovery Key: {self.recovery_key}")
            self.hide() 

    def load_settings(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                data = json.load(f)
                self.target_application_path = data.get("path", "")
                self.encrypted_password = data.get("pass", "")
                self.recovery_key = data.get("recovery", "")
                self.current_lang = data.get("lang", "TR")
                self.lang_box.setCurrentText(self.current_lang)
                self.process_monitor_thread.target_application_path = self.target_application_path

    def show_unlock_screen(self):
        self.unlock_screen = UnlockWindow(self.encrypted_password, self.recovery_key, self.translations[self.current_lang])
        self.unlock_screen.authenticated_signal.connect(self.launch_app)
        self.unlock_screen.show()

    def launch_app(self):
        self.process_monitor_thread.is_authorized = True
        p = subprocess.Popen(self.target_application_path)
        self.wait_thread = AppWaitThread(p)
        self.wait_thread.finished_signal.connect(self.on_app_finished)
        self.wait_thread.start()

    def on_app_finished(self):
        self.process_monitor_thread.is_authorized = False

    def closeEvent(self, event):
      
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("Exe Bariar", "Uygulama arka planda çalışmaya devam ediyor.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def force_quit(self):
        # Gerçekten kapatmak için kullanılan fonksiyon
        self.process_monitor_thread.is_running = False
        QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) 
    window = AppLocker()
    window.show()
    sys.exit(app.exec())