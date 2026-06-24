@echo off
setlocal

set "REPO_DIR=C:\EduevalAI - beta\app\EduevalAI"

if not exist "%REPO_DIR%\update_beta_server.cmd" (
  echo [错误] 未找到更新脚本：%REPO_DIR%\update_beta_server.cmd
  pause
  exit /b 1
)

cd /d "%REPO_DIR%"
call update_beta_server.cmd
