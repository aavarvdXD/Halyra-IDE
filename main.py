from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QMenuBar, QWidget,
    QVBoxLayout, QPushButton, QFileDialog,
    QTabWidget, QDockWidget, QInputDialog, QMessageBox, QLineEdit, QLabel, QHBoxLayout, QStatusBar
)
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtCore import QRegularExpression
import sys, os
import subprocess
import threading
import tempfile
import re

# ---------------------- Syntax Highlighter ---------------------- #
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # ---------- Keywords ----------
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "def", "class", "if", "elif", "else", "try", "except", "finally",
            "for", "while", "return", "import", "from", "as", "with", "pass",
            "break", "continue", "in", "and", "or", "not", "is", "None", "True", "False"
        ]
        for kw in keywords:
            regex = QRegularExpression(rf"\b{kw}\b")
            self.rules.append((regex, keyword_format))

        # ---------- Strings ----------
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))

        # ---------- Comments ----------
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.rules.append((QRegularExpression(r"#.*"), comment_format))

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                start, length = match.capturedStart(), match.capturedLength()
                self.setFormat(start, length, fmt)

# ---------------------- Thread-Safe Console ---------------------- #
class ConsoleSignal(QObject):
    append_text = pyqtSignal(str, QColor)

# ---------------------- Main IDE ---------------------- #
class HalyraIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Halyra IDE")
        self.setGeometry(100, 100, 1000, 700)
        # optional icon file; ignore if not present
        try:
            self.setWindowIcon(QIcon("logo.png"))
        except Exception:
            pass

        # State
        # map editor_widget -> file_path (None if unsaved)
        self.file_paths: dict[QTextEdit, str | None] = {}
        self.dark_mode = True

        # Console signal (create early so threads can always use it)
        self.console_signals = ConsoleSignal()
        self.console_signals.append_text.connect(self.append_console_text)

        # Tabs (create before status bar so update_status can query tabs)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status)
        self.setCentralWidget(self.tabs)

        # Status bar (create right after tabs)
        self.create_status_bar()

        # Create initial tab
        self.new_tab("main.py")

        # Console dock (separated method for clarity)
        self.setup_console()

        # Menu bar and other UI
        self.create_menu_bar()
        self.apply_theme()

    # ---------------------- UI pieces ---------------------- #
    def create_menu_bar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # File Menu
        file_menu = menubar.addMenu("File")
        new_action = QAction("New File", self, shortcut="Ctrl+N", triggered=lambda: self.new_tab("untitled.py"))
        open_action = QAction("Open...", self, shortcut="Ctrl+O", triggered=self.load_file)
        save_action = QAction("Save", self, shortcut="Ctrl+S", triggered=self.save_file)
        save_as_action = QAction("Save As...", self, triggered=self.save_file_as)
        rename_action = QAction("Rename Tab", self, triggered=self.rename_tab)
        file_menu.addActions([new_action, open_action, save_action, save_as_action, rename_action])

        # Run action (in menubar for quick access)
        run_action = QAction("Run Code", self, shortcut="F5", triggered=self.run_code)
        menubar.addAction(run_action)

        # Package Menu
        package_menu = menubar.addMenu("Packages")
        install_action = QAction("Install Package", self, triggered=self.install_package)
        uninstall_action = QAction("Uninstall Package", self, triggered=self.uninstall_package)
        package_menu.addActions([install_action, uninstall_action])

        # Theme
        theme_menu = menubar.addMenu("Theme")
        toggle_action = QAction("Toggle Theme", self, triggered=self.toggle_theme)
        theme_menu.addAction(toggle_action)

    def create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # don't call update_status blindly if tabs not present (they are here)
        self.update_status()

    def setup_console(self):
        # Terminal console (dock)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))

        self.cmd_input = QLineEdit()
        self.cmd_input.returnPressed.connect(self.run_terminal_command)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console.clear)

        terminal_label = QLabel("Terminal Input:")
        terminal_label.setStyleSheet("font-weight: bold;")

        layout = QVBoxLayout()
        layout.addWidget(self.console)
        input_layout = QHBoxLayout()
        input_layout.addWidget(terminal_label)
        input_layout.addWidget(self.cmd_input)
        input_layout.addWidget(clear_btn)
        layout.addLayout(input_layout)

        console_widget = QWidget()
        console_widget.setLayout(layout)

        console_dock = QDockWidget("Terminal", self)
        console_dock.setWidget(console_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, console_dock)

    # ---------------------- Status ---------------------- #
    def update_status(self):
        # defensive checks
        if not hasattr(self, "tabs") or not hasattr(self, "status"):
            return
        index = self.tabs.currentIndex()
        if index == -1:
            self.status.showMessage("")
            return
        editor = self.current_editor()
        if editor is None:
            self.status.showMessage("")
            return
        name = self.tabs.tabText(index)
        path = self.file_paths.get(editor, None) or "Unsaved"
        self.status.showMessage(f"File: {name} | Path: {path}")

    # ---------------------- Tabs / Editor ---------------------- #
    def new_tab(self, name: str, content: str = "") -> QTextEdit:
        editor = QTextEdit()
        editor.setFont(QFont("Consolas", 11))
        
        metrics = editor.fontMetrics()
        tab_width = metrics.horizontalAdvance(' ') * 4  # 4 spaces
        editor.setTabStopDistance(tab_width)
        
        editor.setPlainText(content)
        PythonHighlighter(editor.document())
        index = self.tabs.addTab(editor, name)
        self.tabs.setCurrentIndex(index)
        self.file_paths[editor] = None
        # connect change tracking for future extension (e.g., unsaved marker)
        return editor

    def current_editor(self) -> QTextEdit | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, QTextEdit) else None

    def close_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        widget = self.tabs.widget(index)
        if widget in self.file_paths:
            # optional: check for unsaved changes here
            self.file_paths.pop(widget, None)
        self.tabs.removeTab(index)
        # update status after tab removal
        self.update_status()

    # ---------------------- File Management ---------------------- #
    def save_file(self):
        editor = self.current_editor()
        if editor is None:
            return
        current_path = self.file_paths.get(editor)
        if not current_path:
            return self.save_file_as()
        try:
            with open(current_path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            # update tab text to filename
            self._set_tab_text_for_editor(editor, os.path.basename(current_path))
            self.update_status()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def save_file_as(self):
        editor = self.current_editor()
        if editor is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "Python Files (*.py)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(editor.toPlainText())
                self.file_paths[editor] = path
                self._set_tab_text_for_editor(editor, os.path.basename(path))
                self.update_status()
            except Exception as e:
                QMessageBox.critical(self, "Save As Error", str(e))

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                editor = self.new_tab(os.path.basename(path), content)
                self.file_paths[editor] = path
                self.update_status()
            except Exception as e:
                QMessageBox.critical(self, "Open Error", str(e))

    def rename_tab(self):
        editor = self.current_editor()
        if editor is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "New name:")
        if ok and new_name.strip():
            index = self.tabs.currentIndex()
            self.tabs.setTabText(index, new_name.strip())
            self.update_status()

    def _set_tab_text_for_editor(self, editor: QTextEdit, text: str):
        # find index for a given editor widget and update tab text
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is editor:
                self.tabs.setTabText(i, text)
                return

    # ---------------------- Console ---------------------- #
    def append_console_text(self, text: str, color: QColor = QColor("white")):
        # append colorized text in a thread-safe way (slot connected to signal)
        cursor = self.console.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    # ---------------------- Run Code ---------------------- #
    def run_code(self):
        self.console.clear()  # clear before each run
        editor = self.current_editor()
        if editor is None:
            return
        code = editor.toPlainText()

        # create temp file
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
        tmp_file.write(code.encode("utf-8"))
        tmp_file.close()
        tmp_path = tmp_file.name

        def execute():
            try:
                process = subprocess.Popen(
                    [sys.executable, tmp_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # read stdout & stderr concurrently
                for line in process.stdout:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#B5CEA8"))
                for line in process.stderr:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))
                process.wait()
            except Exception as e:
                self.console_signals.append_text.emit(str(e), QColor("red"))
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        threading.Thread(target=execute, daemon=True).start()

    def run_terminal_command(self):
        self.console.clear()
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.console_signals.append_text.emit(f"> {cmd}", QColor("#9CDCFE"))
        self.cmd_input.clear()

        def execute():
            try:
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in process.stdout:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#B5CEA8"))
                for line in process.stderr:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))
                process.wait()
            except Exception as e:
                self.console_signals.append_text.emit(str(e), QColor("red"))

        threading.Thread(target=execute, daemon=True).start()

    # ---------------------- Pip Management ---------------------- #
    def pip_thread(self, cmd: list[str]):
        def run():
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in process.stdout:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#C586C0"))
                for line in process.stderr:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))
                process.wait()
            except Exception as e:
                self.console_signals.append_text.emit(str(e), QColor("red"))
        threading.Thread(target=run, daemon=True).start()

    def install_package(self):
        package, ok = QInputDialog.getText(self, "Install Package", "Package name:")
        if ok and package.strip():
            self.pip_thread([sys.executable, "-m", "pip", "install", package.strip()])

    def uninstall_package(self):
        package, ok = QInputDialog.getText(self, "Uninstall Package", "Package name:")
        if ok and package.strip():
            self.pip_thread([sys.executable, "-m", "pip", "uninstall", "-y", package.strip()])

    # ---------------------- Theme ---------------------- #
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget { background-color: #1e1e1e; color: #dcdcdc; }
                QTextEdit { background-color: #252526; color: #dcdcdc; }
                QLineEdit { background-color: #2d2d30; color: #dcdcdc; }
                QPushButton { background-color: #3e3e42; color: #fff; border-radius: 4px; }
                QPushButton:hover { background-color: #5a5a5f; }
            """)
        else:
            self.setStyleSheet("")

# ---------------------- Main Entry ---------------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ide = HalyraIDE()
    ide.show()
    sys.exit(app.exec())
