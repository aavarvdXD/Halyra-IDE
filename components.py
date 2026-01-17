"""
Halyra IDE - UI Components
Contains syntax highlighter, line numbers, code editor, and console
"""

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt6.QtGui import (
    QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor,
    QPainter, QTextFormat, QKeyEvent
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRegularExpression, QRect, QSize

# ---------------------- Console Signals ---------------------- #
class ConsoleSignal(QObject):
    append_text = pyqtSignal(str, QColor)
    request_input = pyqtSignal()

# ---------------------- Syntax Highlighter ---------------------- #
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        self.set_theme(dark_mode=True) # Default to dark

    def set_theme(self, dark_mode=True):
        """Update colors dynamically for Light/Dark mode"""
        self.rules = []

        # Define theme-aware colors
        color_kw = "#569CD6" if dark_mode else "#0000FF"  # Blue
        color_str = "#CE9178" if dark_mode else "#A31515" # Red/Brown
        color_com = "#6A9955" if dark_mode else "#008000" # Green

        # Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(color_kw))
        kw_fmt.setFontWeight(700)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "None", "nonlocal",
            "not", "or", "pass", "raise", "return", "True", "try", "while",
            "with", "yield", "async", "await"
        ]
        for kw in keywords:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        # Strings
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor(color_str))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # Comments
        com_fmt = QTextCharFormat()
        com_fmt.setForeground(QColor(color_com))
        com_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#.*"), com_fmt))

        self.rehighlight()

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            i = pattern.globalMatch(text)
            while i.hasNext():
                match = i.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

# ---------------------- Line Number Area ---------------------- #
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

# ---------------------- Code Editor ---------------------- #
class CodeEditor(QPlainTextEdit):
    def __init__(self, is_light=False):
        super().__init__()
        self.is_light = is_light
        self.indent_spaces = 4
        self.line_number_area = LineNumberArea(self)

        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)

        # Use theme-aware colors for line numbers
        bg = QColor("#F0F0F0") if self.is_light else QColor("#2D2D30")
        num_color = QColor("#888888") if self.is_light else QColor("#858585")

        painter.fillRect(event.rect(), bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(num_color)
                painter.drawText(0, int(top), self.line_number_area.width() - 5,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        if self.isReadOnly(): return
        selection = QTextEdit.ExtraSelection()

        # Fixed colors and FullWidthSelection
        color = QColor("#E7F2FF") if self.is_light else QColor("#2C313C")
        selection.format.setBackground(color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            prev_line = cursor.selectedText()
            indent = len(prev_line) - len(prev_line.lstrip(' '))
            if prev_line.rstrip().endswith(':'): indent += self.indent_spaces
            super().keyPressEvent(event)
            self.insertPlainText(' ' * indent)
            return
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText(' ' * self.indent_spaces)
            return
        super().keyPressEvent(event)

# ---------------------- Interactive Console ---------------------- #
class InteractiveConsole(QPlainTextEdit):
    input_submitted = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.waiting_for_input = False
        self.input_start_pos = 0

    def keyPressEvent(self, event):
        if self.waiting_for_input:
            cursor = self.textCursor()
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                cursor.setPosition(self.input_start_pos)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                user_input = cursor.selectedText()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                self.appendPlainText("")
                self.waiting_for_input = False
                self.setReadOnly(True)
                self.input_submitted.emit(user_input)
                return
            elif event.key() == Qt.Key.Key_Backspace:
                if cursor.position() <= self.input_start_pos: return
            elif event.key() == Qt.Key.Key_Left:
                if cursor.position() <= self.input_start_pos: return
            elif event.key() == Qt.Key.Key_Home:
                cursor.setPosition(self.input_start_pos)
                self.setTextCursor(cursor)
                return
        super().keyPressEvent(event)

    def enable_input(self):
        self.waiting_for_input = True
        self.setReadOnly(False)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.input_start_pos = cursor.position()
        self.setFocus()