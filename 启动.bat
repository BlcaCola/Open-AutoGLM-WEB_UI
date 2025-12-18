@echo off
chcp 65001 >nul
echo 启动 Open-AutoGLM Web UI...
REM If there's a virtualenv in the project, try to activate it
if exist "%~dp0.venv\Scripts\activate.bat" (
  call "%~dp0.venv\Scripts\activate.bat"
)
python "%~dp0web\server.py"
pause
