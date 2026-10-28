@echo off
echo ========================================================
echo  Building Forge Standalone Windows Executable (.exe)
echo ========================================================
python -m pip install pyinstaller
python build_exe.py
pause
