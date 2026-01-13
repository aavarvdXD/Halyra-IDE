from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QMenuBar, QWidget,
    QVBoxLayout, QPushButton, QFileDialog, QTabWidget, QDockWidget,
    QInputDialog, QMessageBox, QLineEdit, QLabel, QHBoxLayout, QStatusBar
)
from PyQt6.QtGui import (
    QIcon, QAction, QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor, QFontDatabase
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRegularExpression, QSettings, QEvent
import sys, os, subprocess, threading, tempfile, time, queue

# Handle Windows-specific icon setting safely
try:
    import ctypes

    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


# ---------------------- Syntax Highlighter ---------------------- #
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Keyword formatting
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#569CD6"))

        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "None", "nonlocal",
            "not", "or", "pass", "raise", "return", "True", "try", "while",
            "with", "yield"
        ]
        for kw in keywords:
            regex = QRegularExpression(rf"\b{kw}\b")
            self.rules.append((regex, kw_fmt))

        # Strings
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#CE9178"))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # Comments
        com_fmt = QTextCharFormat()
        com_fmt.setForeground(QColor("#6A9955"))
        com_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#.*"), com_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            i = pattern.globalMatch(text)
            while i.hasNext():
                match = i.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


# ---------------------- Console Signals ---------------------- #
class ConsoleSignal(QObject):
    append_text = pyqtSignal(str, QColor)
    request_input = pyqtSignal()


# ---------------------- Interactive Console ---------------------- #
class InteractiveConsole(QPlainTextEdit):
    """Console that supports interactive input like PyCharm"""
    input_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFont(QFont("Consolas", 10))
        self.waiting_for_input = False
        self.input_start_pos = 0

    def keyPressEvent(self, event):
        if self.waiting_for_input:
            # Only allow editing from input_start_pos onwards
            cursor = self.textCursor()

            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Get input text
                cursor.setPosition(self.input_start_pos)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                user_input = cursor.selectedText()

                # Move to end and add newline
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                self.appendPlainText("")

                # Emit the input
                self.waiting_for_input = False
                self.setReadOnly(True)
                self.input_submitted.emit(user_input)
                return

            elif event.key() == Qt.Key.Key_Backspace:
                if cursor.position() <= self.input_start_pos:
                    return

            elif event.key() == Qt.Key.Key_Left:
                if cursor.position() <= self.input_start_pos:
                    return

            elif event.key() == Qt.Key.Key_Home:
                cursor.setPosition(self.input_start_pos)
                self.setTextCursor(cursor)
                return

        super().keyPressEvent(event)

    def enable_input(self):
        """Enable input mode"""
        self.waiting_for_input = True
        self.setReadOnly(False)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.input_start_pos = cursor.position()
        self.setFocus()


# ---------------------- Main IDE ---------------------- #
class HalyraIDE(QMainWindow):
    """Lightweight Python IDE built with PyQt6."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Halyra IDE")
        self.setGeometry(100, 100, 1000, 700)
        self._apply_icon()

        # --- State ---
        self.file_paths = {}
        self.settings = QSettings("Halyra", "IDE")
        self.dark_mode = self.settings.value("dark_mode", True, type=bool)
        self.current_process = None
        self.input_queue = queue.Queue()

        # --- Signals ---
        self.console_signals = ConsoleSignal()
        self.console_signals.append_text.connect(self.append_console_text)
        self.console_signals.request_input.connect(self.enable_console_input)

        # --- Core UI ---
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status)
        self.setCentralWidget(self.tabs)

        self.create_status_bar()
        self.setup_console()
        self.create_menu_bar()

        # Start with one empty tab
        self.new_tab("main.py")
        self.apply_theme()

    # ---------------------- Setup ---------------------- #
    def _apply_icon(self):
        """Set window icon (Windows-specific handling)"""
        try:
            if HAS_CTYPES and sys.platform == 'win32':
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HalyraIDE")
            if os.path.exists("logo.png"):
                self.setWindowIcon(QIcon("logo.png"))
        except Exception:
            pass

    def create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def setup_console(self):
        self.console = InteractiveConsole()
        self.console.setReadOnly(True)
        self.console.input_submitted.connect(self.on_console_input)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Terminal commands (e.g., pip install, dir, ls)")
        self.cmd_input.returnPressed.connect(self.run_terminal_command)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console.clear)

        layout = QVBoxLayout()
        layout.addWidget(self.console)
        row = QHBoxLayout()
        row.addWidget(QLabel("Terminal Input:"))
        row.addWidget(self.cmd_input)
        row.addWidget(clear_btn)
        layout.addLayout(row)

        console_widget = QWidget()
        console_widget.setLayout(layout)

        dock = QDockWidget("Terminal", self)
        dock.setWidget(console_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def create_menu_bar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # --- File Menu ---
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(QAction("New File", self, shortcut="Ctrl+N", triggered=lambda: self.new_tab("untitled.py")))
        file_menu.addAction(QAction("Open...", self, shortcut="Ctrl+O", triggered=self.load_file))
        file_menu.addAction(QAction("Save", self, shortcut="Ctrl+S", triggered=self.save_file))
        file_menu.addAction(QAction("Save As...", self, triggered=self.save_file_as))
        file_menu.addAction(QAction("Rename Tab", self, triggered=self.rename_tab))

        # --- Run Menu ---
        menubar.addAction(QAction("Run Code (F5)", self, shortcut="F5", triggered=self.run_code))

        # --- Packages Menu ---
        pkg_menu = menubar.addMenu("&Packages")
        pkg_menu.addAction(QAction("Install Package", self, triggered=self.install_package))
        pkg_menu.addAction(QAction("Uninstall Package", self, triggered=self.uninstall_package))

        # --- Theme ---
        theme_menu = menubar.addMenu("&Theme")
        theme_menu.addAction(QAction("Toggle Theme", self, triggered=self.toggle_theme))

    # ---------------------- Tabs ---------------------- #
    def new_tab(self, name: str, content: str = ""):
        editor = QPlainTextEdit()

        # Try to load JetBrains Mono font
        font_loaded = False
        if os.path.exists("JetBrainsMono-Regular.ttf"):
            font_id = QFontDatabase.addApplicationFont("JetBrainsMono-Regular.ttf")
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    editor.setFont(QFont(families[0], 10))
                    font_loaded = True

        # Fallback to Consolas if JetBrains Mono not available
        if not font_loaded:
            editor.setFont(QFont("Consolas", 11))

        editor.setPlainText(content)

        # Keep a reference to prevent GC
        editor.highlighter = PythonHighlighter(editor.document())

        idx = self.tabs.addTab(editor, name)
        self.tabs.setCurrentIndex(idx)
        self.file_paths[editor] = None
        self.update_status()
        return editor

    def current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, QPlainTextEdit) else None

    def close_tab(self, index: int):
        editor = self.tabs.widget(index)
        if not editor:
            return
        self.file_paths.pop(editor, None)
        self.tabs.removeTab(index)
        self.update_status()

    def rename_tab(self):
        editor = self.current_editor()
        if not editor:
            return
        index = self.tabs.currentIndex()
        current_name = self.tabs.tabText(index)
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "New name:", text=current_name)
        if ok and new_name.strip():
            self.tabs.setTabText(index, new_name.strip())
            self.update_status()

    # ---------------------- File Handling ---------------------- #
    def save_file(self):
        editor = self.current_editor()
        if not editor:
            return
        path = self.file_paths.get(editor)
        if not path:
            return self.save_file_as()
        with open(path, "w", encoding="utf-8") as f:
            f.write(editor.toPlainText())
        self.update_status()

    def save_file_as(self):
        editor = self.current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "Python Files (*.py)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            self.file_paths[editor] = path
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))
            self.update_status()

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            editor = self.new_tab(os.path.basename(path), content)
            self.file_paths[editor] = path
            self.update_status()

    # ---------------------- Run Code ---------------------- #
    def run_code(self):
        editor = self.current_editor()
        if not editor:
            QMessageBox.warning(self, "No Editor", "No active editor.")
            return

        code = editor.toPlainText()
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            self.console_signals.append_text.emit(f"SyntaxError: {e}", QColor("red"))
            return

        self.console.clear()
        start = time.time()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode='w', encoding='utf-8')
        tmp.write(code)
        tmp.close()
        tmp_path = tmp.name

        def execute():
            try:
                self.current_process = subprocess.Popen(
                    [sys.executable, "-u", tmp_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=0  # Unbuffered
                )

                # Read stdout in a separate thread
                def read_stdout():
                    buffer = ""
                    while True:
                        char = self.current_process.stdout.read(1)
                        if not char:
                            # End of stream
                            if buffer:
                                self.console_signals.append_text.emit(buffer, QColor("#B5CEA8"))
                            break

                        buffer += char

                        # If we got a newline, flush the buffer
                        if char == '\n':
                            self.console_signals.append_text.emit(buffer.rstrip(), QColor("#B5CEA8"))
                            buffer = ""
                        # If no newline and process still running, might be input prompt
                        elif self.current_process.poll() is None:
                            # Wait a bit to see if more output comes
                            time.sleep(0.05)
                            # If buffer doesn't end with newline, it's probably an input prompt
                            if buffer and not buffer.endswith('\n'):
                                # Flush buffer (without newline) and request input
                                self.console_signals.append_text.emit(buffer, QColor("#B5CEA8"))
                                buffer = ""
                                # Small delay then enable input
                                time.sleep(0.05)
                                self.console_signals.request_input.emit()

                def read_stderr():
                    for line in iter(self.current_process.stderr.readline, ''):
                        if line:
                            self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))

                out_thread = threading.Thread(target=read_stdout, daemon=True)
                err_thread = threading.Thread(target=read_stderr, daemon=True)
                out_thread.start()
                err_thread.start()

                # Monitor process and handle input
                while self.current_process.poll() is None:
                    try:
                        user_input = self.input_queue.get(timeout=0.1)
                        self.current_process.stdin.write(user_input + '\n')
                        self.current_process.stdin.flush()
                    except queue.Empty:
                        pass

                out_thread.join(timeout=1)
                err_thread.join(timeout=1)

                dur = time.time() - start
                self.console_signals.append_text.emit(f"\n[Execution finished in {dur:.2f}s]", QColor("#9CDCFE"))
            except Exception as e:
                self.console_signals.append_text.emit(f"\nError: {e}", QColor("red"))
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                self.current_process = None

        threading.Thread(target=execute, daemon=True).start()

        # Enable input after a short delay (let output print first)
        def delayed_input():
            time.sleep(0.2)
            if self.current_process and self.current_process.poll() is None:
                self.console_signals.request_input.emit()

        threading.Thread(target=delayed_input, daemon=True).start()

    def enable_console_input(self):
        """Enable input in console"""
        if self.current_process and self.current_process.poll() is None:
            self.console.enable_input()

    def on_console_input(self, text):
        """Handle input submitted from console"""
        self.input_queue.put(text)
        # Re-enable input for next prompt
        if self.current_process and self.current_process.poll() is None:
            def delayed_input():
                time.sleep(0.1)
                if self.current_process and self.current_process.poll() is None:
                    self.console_signals.request_input.emit()

            threading.Thread(target=delayed_input, daemon=True).start()

    # ---------------------- Terminal ---------------------- #
    def run_terminal_command(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.console_signals.append_text.emit(f"> {cmd}", QColor("#9CDCFE"))
        self.cmd_input.clear()

        def run():
            try:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in proc.stdout:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#B5CEA8"))
                for line in proc.stderr:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))
                proc.wait()
            except Exception as e:
                self.console_signals.append_text.emit(f"Error: {e}", QColor("red"))

        threading.Thread(target=run, daemon=True).start()

    # ---------------------- Package Management ---------------------- #
    def install_package(self):
        package, ok = QInputDialog.getText(self, "Install Package", "Enter package name:")
        if ok and package.strip():
            self._run_pip_command(["install", package.strip()])

    def uninstall_package(self):
        package, ok = QInputDialog.getText(self, "Uninstall Package", "Enter package name:")
        if ok and package.strip():
            reply = QMessageBox.question(
                self,
                "Confirm Uninstall",
                f"Are you sure you want to uninstall '{package.strip()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._run_pip_command(["uninstall", "-y", package.strip()])

    def _run_pip_command(self, args: list):
        def run():
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "pip"] + args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                for line in process.stdout:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#C586C0"))
                for line in process.stderr:
                    self.console_signals.append_text.emit(line.rstrip(), QColor("#F48771"))
                process.wait()
            except Exception as e:
                self.console_signals.append_text.emit(str(e), QColor("red"))

        threading.Thread(target=run, daemon=True).start()

    # ---------------------- Theme ---------------------- #
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.settings.setValue("dark_mode", self.dark_mode)

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
QWidget { background-color: #1e1e1e; color: #dcdcdc; }
QPlainTextEdit, QLineEdit { background-color: #252526; color: #dcdcdc; }
QPushButton { background-color: #3e3e42; color: #fff; border-radius: 4px; padding: 5px; }
QPushButton:hover { background-color: #5a5a5f; }
QMenuBar { background-color: #2d2d30; color: #dcdcdc; }
QMenuBar::item:selected { background-color: #3e3e42; }
QMenu { background-color: #2d2d30; color: #dcdcdc; }
QMenu::item:selected { background-color: #3e3e42; }
            """)
        else:
            self.setStyleSheet("")

    # ---------------------- Helpers ---------------------- #
    def update_status(self):
        idx = self.tabs.currentIndex()
        if idx == -1:
            self.status.clearMessage()
            return
        editor = self.current_editor()
        path = self.file_paths.get(editor, None) or "Unsaved"
        name = self.tabs.tabText(idx)
        self.status.showMessage(f"{name}  —  {path}")

    def append_console_text(self, text: str, color: QColor = QColor("white")):
        cursor = self.console.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()


# ---------------------- Main Entry ---------------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ide = HalyraIDE()
    ide.show()
    sys.exit(app.exec())
