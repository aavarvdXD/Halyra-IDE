"""
Halyra IDE - UI Components
Contains syntax highlighter, line numbers, code editor, and console
"""

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt6.QtGui import (
    QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor,
    QPainter, QTextFormat
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRegularExpression, QRect, QSize
import time


# ---------------------- Console Signals ---------------------- #
class ConsoleSignal(QObject):
    append_text = pyqtSignal(str, QColor)
    request_input = pyqtSignal()


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
            "with", "yield", "async", "await"
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


# ---------------------- Line Number Area ---------------------- #
class LineNumberArea(QWidget):
    """Widget for displaying line numbers"""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


# ---------------------- Code Editor with Line Numbers ---------------------- #
class CodeEditor(QPlainTextEdit):
    """Text editor with line numbers"""

    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)

        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        """Calculate width needed for line numbers"""
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        """Update the width of line number area"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update line number area when scrolling"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        """Paint the line numbers"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#2d2d30"))  # Dark background for line numbers

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))  # Gray color for numbers
                painter.drawText(0, int(top), self.line_number_area.width() - 3,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        """Highlight the current line"""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2a2a2a")  # Slightly lighter than background
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)


# ---------------------- Interactive Console ---------------------- #
class InteractiveConsole(QPlainTextEdit):
    """Console that supports interactive input like PyCharm"""
    input_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
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