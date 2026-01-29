@echo off
REM Migrate Python Agent from backend\agent\ to top-level agent\
REM Run from project root: scripts\migrate-agent.bat

echo === Migrating Python Agent ===

set SRC=backend\agent
set DEST=agent

REM Ensure destination exists
if not exist "%DEST%" mkdir "%DEST%"

REM Copy core files (skip main.py - already created)
echo Copying core files...
for %%f in (args.py model.py hook.py tool_registry.py __init__.py) do (
    if exist "%SRC%\%%f" (
        copy /Y "%SRC%\%%f" "%DEST%\%%f" >nul
        echo   Copied %%f
    )
)

REM Copy subdirectories
echo Copying subdirectories...
if exist "%SRC%\plan" (
    xcopy /E /I /Y "%SRC%\plan" "%DEST%\plan" >nul
    echo   Copied plan\
)
if exist "%SRC%\tool" (
    xcopy /E /I /Y "%SRC%\tool" "%DEST%\tool" >nul
    echo   Copied tool\
)
if exist "%SRC%\utils" (
    xcopy /E /I /Y "%SRC%\utils" "%DEST%\utils" >nul
    echo   Copied utils\
)

REM Migrate prompts to top-level
if exist "backend\prompts" (
    if not exist "prompts" mkdir "prompts"
    xcopy /E /I /Y "backend\prompts" "prompts" >nul
    echo   Copied prompts\
)

echo.
echo === Migration Complete ===
echo.
echo Files in agent\:
dir /B agent\
echo.
echo Next steps:
echo   1. cd server ^&^& npm install
echo   2. npx prisma generate ^&^& npx prisma migrate dev
echo   3. npm run dev
pause
