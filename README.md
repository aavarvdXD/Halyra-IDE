# Halyra-IDE
An open-source python IDE in development

To run this app you'll need PyQt6 and Python 3.13

After that, you can either download the percompiled .exe at the releases tab or compile the source code

Features:
Core Features
-Tab-based editor with closable, movable tabs
-Python syntax highlighting (via PythonHighlighter)
-Code autocompletion (implemented in CodeEditor)
-Line numbers with current line highlighting
-File Operations
-New file, Open, Save, Save As
-Rename tabs
-Project/folder explorer with tree view (filters hidden files, pycache, venv, etc.)
-Code Execution
-Run Python code (F5) with live output
-Interactive console/terminal with stdin support
-Process management (prevents running multiple scripts simultaneously)
Package Management
-Built-in pip package installer dialog
-Install/uninstall packages
-View installed packages list
UI/UX
-Dark/Light theme toggle with persistent settings
-Custom JetBrains Mono font (falls back to Consolas/Arial)
-Modern scrollbars
-Status bar showing: file path, line/column position, language, encoding
-Toolbar with icon support (different icons for dark/light mode)
Settings
-Dark mode preference (persisted)
-Output speed configuration (ms per character)
-Settings saved via QSettings
Other
-Restart prompt when theme changes
-Console clear button
-UTF-8 encoding support

