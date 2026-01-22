"""
Halyra IDE - Main Application
A lightweight Python IDE built with PyQt6
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QWidget,
    QVBoxLayout, QPushButton, QFileDialog, QTabWidget, QDockWidget,
    QInputDialog, QMessageBox, QLineEdit, QLabel, QHBoxLayout, QStatusBar,
    QToolBar, QTreeWidget, QTreeWidgetItem, QSplitter, QDialog, QCheckBox,
    QSpinBox, QFormLayout, QDialogButtonBox, QHeaderView, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QTextCharFormat, QTextCursor, QFontDatabase
from PyQt6.QtCore import QSettings, Qt, QDir, QFileInfo, QSize, pyqtSignal, QTimer
import sys, os, subprocess, threading, tempfile, time, queue, json, shlex, urllib.request, urllib.parse, re

# Import our components
from components import (
    ConsoleSignal, PythonHighlighter, CodeEditor, InteractiveConsole
)



# Handle Windows-specific icon setting safely
try:
    import ctypes

    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


# ---------------------- Main IDE ---------------------- #
class HalyraIDE(QMainWindow):
    """Lightweight Python IDE built with PyQt6."""
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Halyra", "HalyraIDE")
        self.setWindowTitle("Halyra IDE")
        self.setGeometry(100, 100, 1000, 700)

        # Initialize state first (before UI)
        self.file_paths = {}
        self.dark_mode = self.settings.value("dark_mode", True, type=bool)
        self.current_process = None
        self.process_lock = threading.Lock()
        self.input_queue = queue.Queue()
        self.current_project_path = None
        self.current_working_dir = os.getcwd()
        self.output_buffer_delay = 1 / 60

        # Cache theme stylesheet
        self._cached_stylesheet = None
        self._cached_dark_mode = None

        # Defer heavy initialization
        QTimer.singleShot(0, self._deferred_init)

    def _deferred_init(self):
        """Defer non-critical initialization for faster startup"""
        self.editor_font = self.setup_fonts()
        self._apply_icon()

        self.console_signals = ConsoleSignal()
        self.console_signals.append_text.connect(self.append_console_text)
        self.console_signals.request_input.connect(self.enable_console_input)

        self._setup_ui()
        self.apply_theme()
        self.new_tab("main.py")

    def _setup_ui(self):
        """Consolidated UI setup"""
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setup_file_explorer()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status)
        self.tabs.setMovable(True)

        self.main_splitter.addWidget(self.file_tree_dock)
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(self.main_splitter)
        self.create_toolbar()
        self.create_status_bar()
        self.setup_console()
        self.create_menu_bar()
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

    def setup_fonts(self):
        """Load JetBrains Mono or fallback to Arial/Consolas"""
        font_path = "JetBrainsMono-Regular.ttf"
        font_family = ""

        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]

        if not font_family:
            # Fallback logic: Try Consolas first (better for code), then Arial
            available = QFontDatabase.families()
            if "Consolas" in available:
                font_family = "Consolas"
            else:
                font_family = "Arial"

        return QFont(font_family, 9)

    def create_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # New File
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(lambda: self.new_tab("untitled.py"))
        if os.path.exists("icons/new.png"):
            if self.dark_mode:
                new_action.setIcon(QIcon("icons/new.png"))
            else:
                new_action.setIcon(QIcon("icons/new_light.png"))
        toolbar.addAction(new_action)
        toolbar.addSeparator()

        # Open File
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_file)
        if os.path.exists("icons/open.png"):
            if self.dark_mode:
                open_action.setIcon(QIcon("icons/open.png"))
            else:
                open_action.setIcon(QIcon("icons/open_light.png"))
        toolbar.addAction(open_action)
        toolbar.addSeparator()

        # Save File
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        if os.path.exists("icons/save.png"):
            if self.dark_mode:
                save_action.setIcon(QIcon("icons/save.png"))
            else:
                save_action.setIcon(QIcon("icons/save_light.png"))
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # Run Code
        run_action = QAction("Run", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_code)
        if os.path.exists("icons/run.png"):
            if self.dark_mode:
                run_action.setIcon(QIcon("icons/run.png"))
            else:
                run_action.setIcon(QIcon("icons/run_light.png"))
        toolbar.addAction(run_action)

        toolbar.addSeparator()

        # Open Folder/Project
        folder_action = QAction("Open Folder", self)
        folder_action.triggered.connect(self.open_folder)
        if os.path.exists("icons/folder.png"):
            if self.dark_mode:
                folder_action.setIcon(QIcon("icons/folder.png"))
            else:
                folder_action.setIcon(QIcon("icons/folder_light.png"))
        toolbar.addAction(folder_action)
        toolbar.addSeparator()

        # Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        if os.path.exists("icons/settings.png"):
            if self.dark_mode:
                settings_action.setIcon(QIcon("icons/settings.png"))
            else:
                settings_action.setIcon(QIcon("icons/settings_light.png"))
        toolbar.addAction(settings_action)

    def setup_file_explorer(self):
        """Setup file explorer sidebar"""
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Explorer")
        self.file_tree.itemDoubleClicked.connect(self.on_file_tree_double_click)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.file_tree_dock = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.file_tree)

        self.file_tree_dock.setLayout(layout)
        self.file_tree_dock.setMaximumWidth(300)
        self.file_tree_dock.setMinimumWidth(150)

    def open_folder(self):
        """Open a folder as a project"""
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.current_project_path = folder
            self.load_folder_structure(folder)
            self.setWindowTitle(f"Halyra IDE - {os.path.basename(folder)}")

    def load_folder_structure(self, path):
        """Load folder structure into file tree"""
        self.file_tree.clear()
        root_item = QTreeWidgetItem(self.file_tree)
        root_item.setText(0, os.path.basename(path))
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)

        # Add folder icon if available
        if os.path.exists("icons/folder.png"):
            root_item.setIcon(0, QIcon("icons/folder.png"))

        self._add_folder_contents(root_item, path)
        root_item.setExpanded(True)

    def _add_folder_contents(self, parent_item, path):
        """Recursively add folder contents to tree"""
        try:
            items = os.listdir(path)
            # Sort: folders first, then files
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))

            for item in items:
                # Skip hidden files and common ignore patterns
                if item.startswith('.') or item in ['__pycache__', 'venv', 'env', 'node_modules']:
                    continue

                item_path = os.path.join(path, item)
                tree_item = QTreeWidgetItem(parent_item)
                tree_item.setText(0, item)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                if os.path.isdir(item_path):
                    if os.path.exists("icons/folder.png"):
                        tree_item.setIcon(0, QIcon("icons/folder.png"))
                    self._add_folder_contents(tree_item, item_path)
                else:
                    # Set icon based on file type
                    if item.endswith('.py'):
                        if os.path.exists("icons/python.png"):
                            tree_item.setIcon(0, QIcon("icons/python.png"))
                    elif item.endswith(('.txt', '.md')):
                        if os.path.exists("icons/file.png"):
                            tree_item.setIcon(0, QIcon("icons/file.png"))
        except PermissionError:
            pass

    def on_file_tree_double_click(self, item, column):
        """Handle double click on file tree item"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(path):
            # Open the file
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            editor = self.new_tab(os.path.basename(path), content)
            self.file_paths[editor] = path
            self.update_status()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        old_dark_mode = self.dark_mode

        if dialog.exec():
            # 1. Update local variables from dialog
            new_dark_mode = dialog.dark_mode_checkbox.isChecked()
            new_fps_value = dialog.fps_spinbox.value()

            # 2. SAVE TO DISK IMMEDIATELY
            self.settings.setValue("dark_mode", new_dark_mode)
            self.settings.setValue("output_fps", new_fps_value)
            self.settings.sync()  # Force the OS to write the file now

            # 3. Update current session state
            self.dark_mode = new_dark_mode
            self.output_buffer_delay = new_fps_value / 1000.0

            # 4. Handle Theme Change
            if self.dark_mode != old_dark_mode:
                # This calls restart_app, which kills the process
                self.restart_notice()
            else:
                # Only apply theme if we aren't restarting
                self.apply_theme()
    def create_status_bar(self):
        self.status = QStatusBar()

        # Main status label
        self.status_label = QLabel("")
        self.status.addWidget(self.status_label)

        # Line and column indicator
        self.line_col_label = QLabel("Ln 1, Col 1")
        self.status.addPermanentWidget(self.line_col_label)

        # Language indicator
        self.lang_label = QLabel("Python")
        self.status.addPermanentWidget(self.lang_label)

        # Encoding indicator
        self.encoding_label = QLabel("UTF-8")
        self.status.addPermanentWidget(self.encoding_label)

        self.setStatusBar(self.status)

    def setup_console(self):
        self.console = InteractiveConsole()
        self.console.setReadOnly(True)

        # Apply the same font logic to the console
        self.console.setFont(self.editor_font)

        self.console.input_submitted.connect(self.on_console_input)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console.clear)

        layout = QVBoxLayout()
        layout.addWidget(self.console)
        row = QHBoxLayout()
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
        menubar.hide()
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
        pkg_menu.addAction(QAction("Package Installer", self, triggered=self.open_package_installer))

        # --- Theme ---
        theme_menu = menubar.addMenu("&Theme")
        theme_menu.addAction(QAction("Toggle Theme", self, triggered=self.toggle_theme))

    # ---------------------- Tabs ---------------------- #
    def new_tab(self, name: str, content: str = ""):
        editor = CodeEditor(is_light=not self.dark_mode)

        # Apply the loaded Font
        editor.setFont(self.editor_font)

        editor.cursorPositionChanged.connect(self.update_cursor_position)
        editor.setPlainText(content)

        editor.highlighter = PythonHighlighter(editor.document())
        editor.highlighter.set_theme(dark_mode=self.dark_mode)

        idx = self.tabs.addTab(editor, name)
        self.tabs.setCurrentIndex(idx)
        self.file_paths[editor] = None
        self.update_status()
        return editor

    def update_cursor_position(self):
        """Update cursor position in status bar"""
        editor = self.current_editor()
        if editor:
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.line_col_label.setText(f"Ln {line}, Col {col}")

    def current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

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
    def build_run_command(self):
        editor = self.current_editor()
        if not editor:
            return None

        path = self.file_paths.get(editor)
        if not path:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8")
            tmp.write(editor.toPlainText())
            tmp.close()
            path = tmp.name
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())

        self.current_working_dir = os.path.dirname(path) or os.getcwd()
        return [sys.executable, path]

    def _pump_stdin(self, proc):
        while proc.poll() is None:
            try:
                text = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if proc.stdin:
                    proc.stdin.write(text + "\n")
                    proc.stdin.flush()
            except Exception:
                break

    def run_code(self):
        if self.current_process is not None:
            self.console_signals.append_text.emit(
                "⚠ A process is already running.\n", QColor("yellow")
            )
            return

        command = self.build_run_command()
        if not command:
            return

        self.console.clear()
        self.input_queue = queue.Queue()

        def read_stream(stream, color):
            try:
                for line in stream:
                    self.console_signals.append_text.emit(line, color)
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        def worker():
            proc = None
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=self.current_working_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1
                )

                self.current_process = proc
                self.console_signals.request_input.emit()

                out_thread = threading.Thread(
                    target=read_stream,
                    args=(proc.stdout, QColor("white")),
                    daemon=True
                )
                err_thread = threading.Thread(
                    target=read_stream,
                    args=(proc.stderr, QColor("red")),
                    daemon=True
                )
                in_thread = threading.Thread(
                    target=self._pump_stdin,
                    args=(proc,),
                    daemon=True
                )

                out_thread.start()
                err_thread.start()
                in_thread.start()

                proc.wait()

                out_thread.join()
                err_thread.join()

            except Exception as e:
                self.console_signals.append_text.emit(
                    f"\n❌ Execution error: {e}\n", QColor("red")
                )

            finally:
                if proc:
                    try:
                        if proc.stdin:
                            proc.stdin.close()
                    except Exception:
                        pass

                self.current_process = None

        threading.Thread(target=worker, daemon=True).start()

    def enable_console_input(self):
        """Enable input in console"""
        if self.current_process and self.current_process.poll() is None:
            self.console.enable_input()

    def on_console_input(self, text):
        """Handle input submitted from console"""
        self.input_queue.put(text)
        if self.current_process and self.current_process.poll() is None:
            def delayed_input():
                time.sleep(0.1)
                if self.current_process and self.current_process.poll() is None:
                    self.console_signals.request_input.emit()

            threading.Thread(target=delayed_input, daemon=True).start()

    # ---------------------- Package Management ---------------------- #
    def open_package_installer(self):
        dlg = PackageInstallerDialog(self)
        dlg.exec()

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

    def _run_pip_command(self, args: list, on_finish=None, on_output=None):
        def run():
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "pip"] + args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                for line in process.stdout:
                    if on_output:
                        QTimer.singleShot(0, lambda t=line: on_output(t))
                    self.console_signals.append_text.emit(line, QColor("#C586C0"))
                for line in process.stderr:
                    if on_output:
                        QTimer.singleShot(0, lambda t=line: on_output(t))
                    self.console_signals.append_text.emit(line, QColor("#F48771"))
                process.wait()
            except Exception as e:
                if on_output:
                    QTimer.singleShot(0, lambda t=str(e): on_output(t))
                self.console_signals.append_text.emit(str(e), QColor("red"))
            finally:
                if on_finish:
                    QTimer.singleShot(0, on_finish)

        threading.Thread(target=run, daemon=True).start()

    # ---------------------- Theme ---------------------- #
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.settings.setValue("dark_mode", self.dark_mode)

    def apply_theme(self):
        QApplication.instance().setStyleSheet("")

        if self.dark_mode:
            bg_main = "#1e1e1e"
            bg_alt = "#252526"
            border = "#3e3e42"
            text = "#dcdcdc"
            scroll_thumb = "#424242"
            scroll_hover = "#4f4f54"
            status_bg = "#2d2d30"  # Changed from blue to match theme
        else:
            bg_main = "#F5F5F5"
            bg_alt = "#FAFAFA"
            border = "#D0D0D0"
            text = "#2B2B2B"
            scroll_thumb = "#D0D0D0"
            scroll_hover = "#B0B0B0"
            status_bg = "#EDEDED"

        # Modern Scrollbar CSS
        scrollbar_qss = f"""
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_thumb};
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scroll_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0px; background: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: transparent;
                height: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scroll_thumb};
                min-width: 20px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                width: 0px; background: none;
            }}
        """

        full_qss = f"""
            QWidget {{ background-color: {bg_main}; color: {text}; font-weight: normal; }}
            QPlainTextEdit, QLineEdit {{ 
                background-color: {bg_alt}; 
                color: {text}; 
                border: 1px solid {border}; 
            }}
            QHeaderView::section {{
                background-color: {bg_main};
                color: {text};
                border: 1px solid {border};
            }}
            QMenuBar {{ background-color: {status_bg}; color: {text}; }}
            QToolBar {{ background-color: {status_bg}; border-bottom: 1px solid {border}; }}
            QStatusBar {{ background-color: {status_bg}; color: {text}; border-top: 1px solid {border}; }}
            QStatusBar QLabel {{ color: {text}; }}
            QTabWidget::pane {{ border-top: 1px solid {border}; }}
            QTreeWidget {{ background-color: {bg_alt}; border: none; }}

            /* Apply Scrollbars */
            {scrollbar_qss}

            /* Checkbox styling */
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid {border};
                border-radius: 3px;
                background-color: {bg_alt};
            }}
            QCheckBox::indicator:checked {{
                background-color: #007acc;
                border: 1px solid #007acc;
            }}
        """

        QApplication.instance().setStyleSheet(full_qss)

        # Ensure every existing editor updates its internal 'is_light' state
        for editor in self.findChildren(CodeEditor):
            editor.is_light = not self.dark_mode
            if hasattr(editor, 'highlighter'):
                editor.highlighter.set_theme(dark_mode=self.dark_mode)
            editor.highlight_current_line()
            editor.line_number_area.update()

    # ---------------------- Helpers ---------------------- #
    def restart_app(self):
        """Restarts the current program."""
        self.settings.sync() # One last sync for safety
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def update_status(self):
        idx = self.tabs.currentIndex()
        if idx == -1:
            self.status_label.clear()
            return
        editor = self.current_editor()
        path = self.file_paths.get(editor, None) or "Unsaved"
        name = self.tabs.tabText(idx)
        self.status_label.setText(f"{name}  —  {path}")
        self.update_cursor_position()

    def append_console_text(self, text: str, color: QColor = QColor("white")):
        """Optimized console text appending"""
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Batch format setting
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(text, fmt)

        # Only scroll if near bottom (avoids expensive scroll on every update)
        scrollbar = self.console.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        if at_bottom:
            self.console.ensureCursorVisible()

    def restart_notice(self):
        msg = QMessageBox()
        msg.setWindowTitle("Restart Required")
        msg.setText("Please restart the application to apply changes.")
        msg.setIcon(QMessageBox.Icon.Information)

        restart_btn = msg.addButton("Restart", QMessageBox.ButtonRole.AcceptRole)
        close_btn = msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)

        msg.setDefaultButton(restart_btn)

        msg.exec()
        if msg.clickedButton() == restart_btn:
            self.restart_app()
        else:
            msg.close()


# ---------------------- Settings Dialog ---------------------- #
class SettingsDialog(QDialog):
    """Settings dialog for the IDE"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 200)

        layout = QFormLayout()

        # Dark mode checkbox
        self.dark_mode_checkbox = QCheckBox()
        self.dark_mode_checkbox.setChecked(parent.dark_mode if parent else True)
        layout.addRow("Dark Mode:", self.dark_mode_checkbox)

        # Output FPS setting
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(10, 120)
        self.fps_spinbox.setValue(int(1000 * parent.output_buffer_delay) if parent else 17)
        self.fps_spinbox.setSuffix(" ms per character")
        layout.addRow("Output Speed:", self.fps_spinbox)

        btn_style = """
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #2D7DFF;
                border-radius: 4px;
                background-color: transparent;
                color: #2D7DFF;
            }
            QPushButton:hover {
                background-color: #3E8CFF;
                color: white;
            }
        """

        pkg_btn = QPushButton("Package Installer")
        pkg_btn.setStyleSheet(btn_style)
        pkg_btn.clicked.connect(lambda: parent.open_package_installer() if parent else None)
        layout.addRow("Packages:", pkg_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(btn_style)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)


# ---------------------- Package Installer Dialog ---------------------- #
class PackageInstallerDialog(QDialog):
    installed_loaded = pyqtSignal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Package Installer")
        self.resize(400, 350)
        self.parent = parent

        self.installed_loaded.connect(self._on_installed_loaded)

        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("Enter package name (e.g. requests or numpy==1.24.0)")

        self.install_btn = QPushButton("Install")
        self.uninstall_btn = QPushButton("Uninstall")
        self.refresh_btn = QPushButton("Refresh")

        self._style_buttons([self.install_btn, self.uninstall_btn, self.refresh_btn])

        self.install_btn.clicked.connect(self._install)
        self.uninstall_btn.clicked.connect(self._uninstall)
        self.refresh_btn.clicked.connect(self.refresh_installed)

        self.installed_list = QListWidget()
        self.installed_list.itemClicked.connect(self._on_select_installed)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)

        main = QVBoxLayout()
        main.addWidget(QLabel("Package name:"))
        main.addWidget(self.package_input)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.install_btn)
        btn_row.addWidget(self.uninstall_btn)
        btn_row.addWidget(self.refresh_btn)
        main.addLayout(btn_row)

        main.addWidget(QLabel("Installed packages:"))
        main.addWidget(self.installed_list)
        main.addWidget(self.status_label)

        self.setLayout(main)
        self.refresh_installed()

    def _style_buttons(self, buttons):
        accent = "#2D7DFF"
        hover = "#3E8CFF"
        for btn in buttons:
            btn.setMinimumHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 6px 12px;
                    border: 1px solid {accent};
                    border-radius: 4px;
                    background-color: transparent;
                    color: {accent};
                }}
                QPushButton:hover {{
                    background-color: {hover};
                    color: white;
                }}
            """)

    def _set_status(self, text: str):
        self.status_label.setText(text.strip() or "Ready")

    def refresh_installed(self):
        self._set_status("Loading installed packages...")
        threading.Thread(target=self._load_installed, daemon=True).start()

    def _load_installed(self):
        try:
            output = subprocess.check_output(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                text=True,
                stderr=subprocess.STDOUT
            )
            pkgs = json.loads(output)
            self.installed_loaded.emit(pkgs, "")
        except Exception as e:
            self.installed_loaded.emit([], str(e))

    def _on_installed_loaded(self, packages, error):
        self.installed_list.clear()
        if error:
            self._set_status(f"Error: {error}")
            return

        # Filter out core packages that shouldn't be uninstalled
        # Note: pip normalizes names (e.g., PyQt6-sip becomes pyqt6-sip or pyqt6_sip)
        protected_packages = {"pyqt6", "pyqt6-qt6", "pyqt6-sip", "pyqt6_sip"}
        filtered_packages = [
            pkg for pkg in packages
            if pkg["name"].lower().replace("-", "_") not in {p.replace("-", "_") for p in protected_packages}
        ]

        for pkg in sorted(filtered_packages, key=lambda p: p["name"].lower()):
            item = QListWidgetItem(f'{pkg["name"]}  ({pkg["version"]})')
            item.setData(Qt.ItemDataRole.UserRole, pkg["name"])
            self.installed_list.addItem(item)
        self._set_status(f"{len(filtered_packages)} packages installed.")

    def _on_select_installed(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        self.package_input.setText(name)

    def _install(self):
        name = self.package_input.text().strip()
        if not name or not self.parent:
            return
        self._set_status(f"Installing {name} ...")
        self.parent._run_pip_command(
            ["install", name],
            on_finish=self.refresh_installed,
            on_output=self._set_status
        )

    def _uninstall(self):
        name = self.package_input.text().strip()
        if not name or not self.parent:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Uninstall",
            f"Uninstall '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._set_status(f"Uninstalling {name} ...")
            self.parent._run_pip_command(
                ["uninstall", "-y", name],
                on_finish=self.refresh_installed,
                on_output=self._set_status
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HalyraIDE()
    window.show()
    sys.exit(app.exec())
