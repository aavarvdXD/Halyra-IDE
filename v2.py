import sys, subprocess, keyword, re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QTabWidget, QInputDialog,
    QPlainTextEdit, QCompleter, QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QPainter, QIcon
from PyQt6.QtCore import Qt, QRect, QSize
import subprocess
import sys

class PackageManager:
    def __init__(self, parent):
        self.parent = parent

    def install_package(self):
        # Ask user for package name
        package, ok = QInputDialog.getText(self.parent, "Install Package", "Package name:")
        if ok and package.strip():
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package.strip()],
                    capture_output=True, text=True
                )
                # Show output or errors
                QMessageBox.information(
                    self.parent, f"Install {package.strip()}",
                    process.stdout + process.stderr
                )
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

    def uninstall_package(self):
        # Optional: uninstall packages the same way
        package, ok = QInputDialog.getText(self.parent, "Uninstall Package", "Package name:")
        if ok and package.strip():
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", "-y", package.strip()],
                    capture_output=True, text=True
                )
                QMessageBox.information(
                    self.parent, f"Uninstall {package.strip()}",
                    process.stdout + process.stderr
                )
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

# ---------------- Syntax Highlighter ---------------- #
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.keywords = keyword.kwlist
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569CD6"))
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#CE9178"))
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))

    def highlightBlock(self, text):
        # Keywords
        for word in self.keywords:
            for match in re.finditer(rf'\b{word}\b', text):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, self.keyword_format)
        # Strings
        for match in re.finditer(r'(["\'])(?:(?=(\\?))\2.)*?\1', text):
            start, end = match.start(), match.end()
            self.setFormat(start, end - start, self.string_format)
        # Comments
        comment_index = text.find("#")
        if comment_index != -1:
            self.setFormat(comment_index, len(text) - comment_index, self.comment_format)


# ---------------- Editor with Line Numbers ---------------- #
class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.setFont(QFont("Consolas", 11))

        # Auto-indent
        self.keywords = keyword.kwlist

        # Basic completer (keywords only)
        self.completer = QCompleter(self.keywords)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2a2d2e"))
            selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def keyPressEvent(self, event):
        # Auto-indent
        if event.key() == Qt.Key.Key_Return:
            cursor = self.textCursor()
            cursor.insertText("\n" + " " * (len(cursor.block().text()) - len(cursor.block().text().lstrip())))
        else:
            super().keyPressEvent(event)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


# ---------------- IDE Main Window ---------------- #
class Halyra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Halyra Beta edition")
        self.setWindowIcon(QIcon("logo.png"))
        self.setGeometry(100, 100, 900, 650)
        self.dark_mode = True

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self.run_code)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_file)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_file)
        rename_btn = QPushButton("Rename Tab")
        rename_btn.clicked.connect(self.rename_tab)
        theme_btn = QPushButton("Toggle Theme")
        theme_btn.clicked.connect(self.toggle_theme)

        button_layout.addWidget(run_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(load_btn)
        button_layout.addWidget(rename_btn)
        button_layout.addWidget(theme_btn)

        # Output
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(QLabel("Output:"))
        layout.addWidget(self.output)

        # Start
        self.new_tab("main.py")
        self.apply_theme()

    def new_tab(self, name):
        editor = CodeEditor()
        PythonHighlighter(editor.document())
        self.tabs.addTab(editor, name)
        self.tabs.setCurrentWidget(editor)

    def current_editor(self):
        return self.tabs.currentWidget()

    def run_code(self):
        code = self.current_editor().toPlainText()
        try:
            # Save to a temporary file
            import tempfile, os
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
            tmp_file.write(code.encode("utf-8"))
            tmp_file.close()

            # Run in a separate process so Tkinter windows can open safely
            import subprocess, sys
            process = subprocess.Popen(
                [sys.executable, tmp_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            # Show output in the separate console
            self.output.setPlainText(stdout + stderr)

            # Optional: delete temp file
            os.unlink(tmp_file.name)

        except Exception as e:
            self.output.setPlainText(str(e))

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Python Files (*.py)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current_editor().toPlainText())
            self.tabs.setTabText(self.tabs.currentIndex(), path.split("/")[-1])

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.new_tab(path.split("/")[-1])
            self.current_editor().setPlainText(content)

    def rename_tab(self):
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "New filename:")
        if ok and new_name.strip():
            self.tabs.setTabText(self.tabs.currentIndex(), new_name.strip() + ".py")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget { background-color: #1e1e1e; color: #dcdcdc; }
                QTextEdit, QPlainTextEdit { background-color: #252526; color: #dcdcdc; }
                QPushButton { background-color: #333333; color: #ffffff; }
                QPushButton:hover { background-color: #444444; }
            """)
        else:
            self.setStyleSheet("")


# ---------------- Run App ---------------- #
app = QApplication(sys.argv)
ide = Halyra()
ide.show()
sys.exit(app.exec())
