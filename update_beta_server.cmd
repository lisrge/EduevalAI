@echo off
setlocal

set "TEST_ROOT=C:\EduevalAI - beta"
set "REPO_DIR=%TEST_ROOT%\app\EduevalAI"
set "BACKEND_DIR=%REPO_DIR%\backend"
set "FRONTEND_DIR=%REPO_DIR%\fronted"
set "PUBLIC_PORT=80"

set "GIT_EXE="
if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
if not defined GIT_EXE if exist "C:\Program Files\Git\bin\git.exe" set "GIT_EXE=C:\Program Files\Git\bin\git.exe"
if not defined GIT_EXE for /f "delims=" %%I in ('where git 2^>nul') do if not defined GIT_EXE set "GIT_EXE=%%~fI"

if not defined GIT_EXE (
  echo [错误] 未找到 Git，请先安装 Git 或加入 PATH
  pause
  exit /b 1
)

if not exist "%REPO_DIR%\.git" (
  echo [错误] 未找到测试版仓库目录：%REPO_DIR%
  pause
  exit /b 1
)

echo [1/6] 停止 80 端口旧进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PUBLIC_PORT%') do taskkill /F /PID %%a >nul 2>nul

echo [2/6] 拉取最新代码...
cd /d "%REPO_DIR%"
"%GIT_EXE%" fetch origin
if errorlevel 1 goto :git_failed
"%GIT_EXE%" pull --ff-only origin main
if errorlevel 1 goto :git_failed
goto :git_ok

:git_failed
echo [错误] Git 拉取失败，请先处理本地冲突或网络问题
pause
exit /b 1

:git_ok
echo [3/6] 安装后端依赖...
cd /d "%BACKEND_DIR%"
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [错误] 后端依赖安装失败
  pause
  exit /b 1
)

echo [4/6] 安装前端依赖...
cd /d "%FRONTEND_DIR%"
call npm install
if errorlevel 1 (
  echo [错误] 前端依赖安装失败
  pause
  exit /b 1
)

echo [5/6] 重新打包前端...
set "VUE_APP_EDUEVAL_API_BASE=/api"
call npm run build
if errorlevel 1 (
  echo [错误] 前端打包失败
  pause
  exit /b 1
)

echo [6/6] 重启测试版...
start "EduevalAI Beta Web 80" cmd /k "cd /d %BACKEND_DIR% && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 80"

echo.
echo [完成] 已更新并重启测试版
echo 访问地址: http://211.87.232.160/
echo 如果新增了 Basic Auth，请使用 backend\.env 中的账号密码访问
pause
exit /b 0
