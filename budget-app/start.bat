@echo off
chcp 65001 >nul
title 预算与支出管理系统

echo ========================================
echo   预算与支出管理系统 - 启动中...
echo ========================================
echo.

:: 设置 Python 路径
set PYTHON=C:/Users/admin/AppData/Local/Programs/Python/Python312/python.exe

:: 检查 Python
if not exist "%PYTHON%" (
    echo [错误] 未找到 Python: %PYTHON%
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
"%PYTHON%" -m pip install -r requirements.txt -q

echo [2/3] 初始化数据库...
"%PYTHON%" init_db.py

echo [3/3] 启动服务器...
echo.
echo   服务器地址: http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

start "" http://localhost:5000
"%PYTHON%" app.py
pause
