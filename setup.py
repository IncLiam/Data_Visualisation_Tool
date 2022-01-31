import sys
import os
from cx_Freeze import setup, Executable

python_dir = os.path.dirname(os.path.dirname(os.__file__))

# Dependencies are automatically detected, but it might need fine tuning.
# "packages": ["os"] is used as example only
build_exe_options = {"packages": ["matplotlib", "pyqtgraph", "vispy", "pyqt5", "numpy", "time", "serial",
                                  "aioprocessing", "multiprocessing"],
                     "excludes": [],
                     "includes":  [],
                     "include_files":
                         [os.path.join(python_dir, "python3.dll"),
                          os.path.join(python_dir, "vcruntime140.dll"),
                          os.path.join(python_dir, "python37.dll"),
                          "vispy_pyqt_gui/images"],
                     "build_exe": "Hyve GUI",
                     'path': [os.path.abspath('vispy_pyqt_gui')] + sys.path}

# base="Win32GUI" should be used only for Windows GUI app
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name = "HyveGUI",
    version = "0.1",
    description = "Data visualisation tool",
    options = {"build_exe": build_exe_options},
    executables = [Executable(r"vispy_pyqt_gui/main.py",
                              base=base,
                              icon="vispy_pyqt_gui/images/hyve_icon.ico",
                              targetName="Hyve_GUI")]
)