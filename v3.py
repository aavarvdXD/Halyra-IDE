from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QMenuBar, QMenu, QWidget,
    QHBoxLayout, QPushButton, QSizePolicy, QWidgetAction, QFileDialog,
    QTabWidget, QDockWidget
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt
import sys
import subprocess


class HalyraIDE(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Halyra IDE Beta edition")
        self.setGeometry(100, 100, 900, 650)
        self.setWindowIcon(QIcon("logo.png"))
        self.dark_mode = True

        # Tabs for multiple files
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.new_tab("main.py")
        # Console dock
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console_dock = QDockWidget("Console", self)
        self.console_dock.setWidget(self.console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)

        self.create_menu_bar()
        self.apply_theme()

    def create_menu_bar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New File", self)
        new_action.triggered.connect(lambda: self.new_tab("untitled.py"))
        file_menu.addAction(new_action)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        rename_action = QAction("Rename File", self)
        rename_action.triggered.connect(self.rename_tab)
        file_menu.addAction(rename_action)

        # Packages menu
        package_menu = menubar.addMenu("Packages")
        install_action = QAction("Install Package", self)
        install_action.triggered.connect(self.install_package)
        uninstall_action = QAction("Uninstall Package", self)
        uninstall_action.triggered.connect(self.uninstall_package)
        package_menu.addAction(install_action)
        package_menu.addAction(uninstall_action)

        # Theme menu
        theme_menu = menubar.addMenu("Theme")
        toggle_action = QAction("Toggle Theme", self)
        toggle_action.triggered.connect(self.toggle_theme)
        theme_menu.addAction(toggle_action)

        # Run button
        run_action = QAction("Run", self)
        run_action.triggered.connect(self.run_code)
        menubar.addAction(run_action)

    def new_tab(self, name):
        editor = QTextEdit()
        self.tabs.addTab(editor, name)
        self.tabs.setCurrentWidget(editor)

    def current_editor(self):
        return self.tabs.currentWidget()

    def run_code(self):
        code = self.current_editor().toPlainText()
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
            tmp_file.write(code.encode("utf-8"))
            tmp_file.close()

            process = subprocess.Popen(
                [sys.executable, tmp_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            self.console.setPlainText(stdout + stderr)

            os.unlink(tmp_file.name)
        except Exception as e:
            self.console.setPlainText(str(e))

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Python Files (*.py)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current_editor().toPlainText())
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.new_tab(os.path.basename(path))
            self.current_editor().setPlainText(content)

    def rename_tab(self):
        new_name, ok = QInputDialog.getText(self, "Rename File", "New filename:")
        if ok and new_name.strip():
            self.tabs.setTabText(self.tabs.currentIndex(), new_name.strip() + ".py")

    # ---------------- Packages ---------------- #
    def install_package(self):
        from PyQt6.QtWidgets import QInputDialog
        package, ok = QInputDialog.getText(self, "Install Package", "Package name:")
        if ok and package.strip():
            process = subprocess.run(
                [sys.executable, "-m", "pip", "install", package.strip()],
                capture_output=True, text=True
            )
            QMessageBox.information(self, f"Install {package.strip()}", process.stdout + process.stderr)

    def uninstall_package(self):
        from PyQt6.QtWidgets import QInputDialog
        package, ok = QInputDialog.getText(self, "Uninstall Package", "Package name:")
        if ok and package.strip():
            process = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", package.strip()],
                capture_output=True, text=True
            )
            QMessageBox.information(self, f"Uninstall {package.strip()}", process.stdout + process.stderr)

    # ---------------- Theme ---------------- #
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget { background-color: #1e1e1e; color: #dcdcdc; }
                QTextEdit { background-color: #252526; color: #dcdcdc; }
            """)
        else:
            self.setStyleSheet("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ide = HalyraIDE()
    ide.show()
    sys.exit(app.exec())
