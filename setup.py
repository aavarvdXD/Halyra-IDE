import os, sys
from cx_Freeze import setup, Executable
import PyQt6

# Correct path to Qt6 platforms folder
qt_platforms_path = os.path.join(
    os.path.dirname(PyQt6.__file__),
    "Qt6", "plugins", "platforms"
)

build_exe_options = {
    "packages": ["os", "sys", "tempfile", "subprocess", "PyQt6"],
    "includes": [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets"
    ],
    "include_files": [
        "logo.png",
        (qt_platforms_path, "platforms")  # copy platforms folder
    ],
}

setup(
    name="Halyra IDE",
    version="1.1",
    description="Halyra IDE: Your Python Friend",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base="Win32GUI", icon="logo.png")],
)
