"""
Halyra IDE - UI Components
Contains syntax highlighter, line numbers, code editor, and console
"""

from PyQt6.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QCompleter, QAbstractItemView
)
from PyQt6.QtGui import (
    QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor,
    QPainter, QTextFormat, QKeyEvent, QFont, QFontDatabase,
    QGuiApplication, QAction, QFontMetricsF
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QRegularExpression, QRect, QSize, QStringListModel
)
import sys, os

# --- Global Font Setup for Halyra Components ---
def get_halyra_font(size=9):
    font_path = "JetBrainsMono-Regular.ttf"
    family = "Consolas"  # Default fallback
    if QGuiApplication.instance() is not None and os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            family = QFontDatabase.applicationFontFamilies(font_id)[0]

    font = QFont(family, size)
    font.setWeight(QFont.Weight.Normal)
    font.setFixedPitch(True)
    return font


GLOBAL_FONT = get_halyra_font(9)

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
        color_kw = "#569CD6" if dark_mode else "#0000FF"
        color_str = "#CE9178" if dark_mode else "#A31515"
        color_com = "#6A9955" if dark_mode else "#008000"

        # Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(color_kw))
        kw_fmt.setFontWeight(QFont.Weight.Normal)
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
        self. indent_spaces = 4
        self.line_number_area = LineNumberArea(self)

        self.setFont(GLOBAL_FONT)

        # Cache font metrics
        self._font_metrics = QFontMetricsF(self.font())
        self._char_width = self._font_metrics.horizontalAdvance(" ")
        self.setTabStopDistance(self._char_width * 4)

        # Cache completer width
        self. completer_width = int(self._char_width * 25)

        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

        # Use queued connections for less critical updates
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        self._setup_completer()

    def _setup_completer(self):
        """Separate completer setup for cleaner code"""
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

        popup = self.completer.popup()
        bg_col = "#FFFFFF" if self.is_light else "#252526"
        txt_col = "#000000" if self.is_light else "#CCCCCC"
        sel_bg = "#0078D7" if self.is_light else "#094771"
        border = "#C0C0C0" if self.is_light else "#454545"

        popup.setStyleSheet(f"""
            QAbstractItemView {{
                background-color: {bg_col}; color: {txt_col};
                selection-background-color: {sel_bg}; selection-color: #FFFFFF;
                border: 1px solid {border}; outline: 0;
            }}
            QAbstractItemView::item {{ padding: 4px 5px; min-height: 20px; }}
        """)

        # Keywords as tuple (immutable, faster iteration)
        keywords = (
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "case", "class", "continue", "def", "del", "elif", "else",
            "except", "finally", "for", "from", "global", "if", "import", "in",
            "is", "lambda", "match", "nonlocal", "not", "or", "pass", "raise",
            "return", "try", "while", "with", "yield", "abs", "aiter", "all",
            "anext", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
            "bytes", "callable", "chr", "classmethod", "compile", "complex",
            "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
            "filter", "float", "format", "frozenset", "getattr", "globals",
            "hasattr", "hash", "help", "hex", "id", "input", "int", "isinstance",
            "issubclass", "iter", "len", "list", "locals", "map", "max",
            "memoryview", "min", "next", "object", "oct", "open", "ord", "pow",
            "print", "property", "range", "repr", "reversed", "round", "set",
            "setattr", "slice", "sorted", "staticmethod", "str", "sum", "super",
            "tuple", "type", "vars", "zip", "__import__", "BaseException",
            "Exception", "ArithmeticError", "AssertionError", "AttributeError",
            "BufferError", "EOFError", "ImportError", "LookupError", "IndexError",
            "KeyError", "MemoryError", "NameError", "OSError", "OverflowError",
            "RuntimeError", "StopIteration", "StopAsyncIteration", "SyntaxError",
            "IndentationError", "TabError", "SystemError", "TypeError",
            "UnboundLocalError", "ValueError", "ZeroDivisionError",
            "FileNotFoundError", "ModuleNotFoundError", "PermissionError",
            "TimeoutError", "__init__", "__new__", "__del__", "__str__", "__repr__",
            "__len__", "__getitem__", "__setitem__", "__delitem__", "__iter__",
            "__next__", "__contains__", "__call__", "__enter__", "__exit__",
            "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__", "__mod__",
            "__pow__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
            "__and__", "__or__", "__xor__", "__bool__", "__hash__", "__copy__",
            "__deepcopy__", "__await__", "__aiter__", "__anext__", "sys", "os",
            "math", "cmath", "random", "time", "datetime", "json", "csv", "pickle",
            "re", "pathlib", "shutil", "glob", "threading", "multiprocessing",
            "asyncio", "subprocess", "logging", "argparse", "typing", "dataclasses",
            "functools", "itertools", "operator", "collections", "inspect",
            "platform"
        )
        self.completer.setModel(QStringListModel(list(keywords), self.completer))

    def _is_definition_context(self):
        """Check if cursor is in a context where user is naming something (not needing autocomplete)"""
        cursor = self.textCursor()
        line = cursor.block().text()
        col = cursor.columnNumber()
        text_before_cursor = line[:col]

        # Strip to get clean text
        stripped = text_before_cursor.lstrip()

        # Check if defining a function: "def " followed by name
        if stripped.startswith("def ") and "(" not in stripped:
            return True

        # Check if defining a class: "class " followed by name
        if stripped.startswith("class ") and "(" not in stripped and ":" not in stripped:
            return True

        # Check if in import statement: "import x" or "from x import y"
        if stripped.startswith("import "):
            return True
        if stripped.startswith("from ") and " import " not in stripped:
            return True
        # After "from x import " - user is typing what to import
        if " import " in stripped and stripped.index(" import ") < len(stripped) - 8:
            after_import = stripped.split(" import ")[-1]
            # Allow if typing after import but no comma context
            if "," not in after_import or after_import.rstrip().endswith(","):
                return True

        # Check if using "as" alias: "import x as " or "from x import y as "
        if stripped.rstrip().endswith(" as") or " as " in stripped.split()[-1:]:
            words = stripped.split()
            if len(words) >= 2 and words[-1] == "as":
                return True
            if len(words) >= 1 and " as " in text_before_cursor:
                # Check if cursor is right after "as "
                as_pos = text_before_cursor.rfind(" as ")
                if as_pos != -1:
                    after_as = text_before_cursor[as_pos + 4:]
                    # If there's no space after the alias name, still defining
                    if " " not in after_as.strip():
                        return True

        # Check for variable assignment: "varname = " - cursor is right after "="
        # We want to NOT suppress when typing the VALUE, only when typing the NAME
        # So check if we're BEFORE an "=" sign on this line
        if "=" in line:
            eq_pos = line.index("=")
            # If cursor is before the "=" and not in a comparison
            if col <= eq_pos:
                # Make sure it's not == or != or <= or >=
                if eq_pos == 0 or line[eq_pos - 1] not in "!<>=":
                    if eq_pos + 1 >= len(line) or line[eq_pos + 1] != "=":
                        return True

        # Check for "for x in": defining loop variable
        if stripped.startswith("for ") and " in " not in stripped:
            return True

        # Check for "except X as ": defining exception alias
        if stripped.startswith("except ") and " as " in stripped:
            as_pos = stripped.rfind(" as ")
            after_as = stripped[as_pos + 4:]
            if ":" not in after_as:
                return True

        # Check for "with x as ": defining context manager alias
        if stripped.startswith("with ") and " as " in stripped:
            as_pos = stripped.rfind(" as ")
            after_as = stripped[as_pos + 4:]
            if ":" not in after_as and "," not in after_as:
                return True

        return False

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 8 + int(self._char_width * digits) if hasattr(self, '_char_width') else 50

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
        painter.setFont(GLOBAL_FONT)

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

        color = QColor("#E7F2FF") if self.is_light else QColor("#2C313C")
        selection.format.setBackground(color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def insert_completion(self, completion):
        if self.completer.widget() != self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def keyPressEvent(self, event: QKeyEvent):
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab,
                               Qt.Key.Key_Backtab):
                event.ignore()
                return

        # Fix 1: Soft Tabs (Replaces mixed tabs/spaces issues)
        if event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.insertPlainText("    ")
            return

        # Fix 2: Auto-Indentation on Enter
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            cursor = self.textCursor()
            current_line = cursor.block().text()

            # Calculate leading whitespace
            indentation = ""
            for char in current_line:
                if char.isspace():
                    indentation += char
                else:
                    break

            # Add extra indent if line ends with colon
            if current_line.rstrip().endswith(":"):
                indentation += "    "

            # Perform the enter + indent
            super().keyPressEvent(event)
            self.insertPlainText(indentation)
            return

        is_shortcut = (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Space)

        # Standard processing
        super().keyPressEvent(event)

        # Automatic popup logic
        ctrl_or_shift = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        if not self.completer or (ctrl_or_shift and not is_shortcut):
            return

        has_modifier = (event.modifiers() != Qt.KeyboardModifier.NoModifier) and not is_shortcut

        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        completion_prefix = tc.selectedText()

        # Don't show autocomplete when in definition context (naming variables, functions, classes, imports)
        if self._is_definition_context():
            self.completer.popup().hide()
            return

        if (is_shortcut or (len(completion_prefix) > 0 and not has_modifier)):
            self.completer.setCompletionPrefix(completion_prefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

            cr = self.cursorRect()
            # Updated to use fixed width calculated in __init__
            cr.setWidth(self.completer_width)
            self.completer.complete(cr)
        else:
            self.completer.popup().hide()

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
