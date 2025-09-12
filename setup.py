import sys, os
from cx_Freeze import setup, Executable

# Path to PyQt6 plugins (platforms)
qt_platforms_path = os.path.join(
    os.path.dirname(sys.executable),
    "Lib", "site-packages", "PyQt6", "Qt6", "plugins", "platforms"
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
        (qt_platforms_path, "platforms")  # copy the platforms folder
    ],
}

setup(
    name="Halyra IDE",
    version="0.3",
    description="Halyra IDE Beta Edition",
    options={"build_exe": build_exe_options},
    executables=[
        Executable("v3.py", base="Win32GUI", icon="logo.png")
    ],
)
