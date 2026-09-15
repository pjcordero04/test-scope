@echo off
title UpdateGoldenLimits - Sync from GitLab
echo ============================================
echo   Update Golden Limits from GitLab
echo ============================================
echo.

:: --- Check for Git ---
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not on PATH.
    echo Please install Git from https://git-scm.com/download/win
    echo Then re-run this script.
    pause
    exit /b 1
)
echo [OK] Git is installed.

:: --- Clone or Pull ---
if exist "C:\si_test_limits\.git" (
    echo [INFO] GitLab repo already cloned at C:\si_test_limits
    echo        Pulling latest changes...
    echo.

    :: Remove read-only so git can update files
    attrib -R "C:\si_test_limits\*.json" /S >nul 2>&1

    :: Fetch and force-reset to match GitLab exactly
    git -C "C:\si_test_limits" fetch origin
    if %errorlevel% neq 0 (
        echo [ERROR] git fetch failed. Check network connection.
        pause
        exit /b 1
    )
    git -C "C:\si_test_limits" reset --hard origin/main
    if %errorlevel% neq 0 (
        echo [ERROR] git reset failed.
        pause
        exit /b 1
    )

    :: Set files back to read-only
    attrib +R "C:\si_test_limits\*.json" /S >nul 2>&1

    echo [OK] Golden limits updated successfully.
) else (
    echo [SETUP] Cloning golden limits repo from GitLab...
    echo.
    :: NOTE: Replace <DEPLOY_TOKEN_USER> and <DEPLOY_TOKEN> with your GitLab deploy token credentials
    git clone "https://<DEPLOY_TOKEN_USER>:<DEPLOY_TOKEN>@gitlab.com/Molex/tis/cmsbu/mats/si_test_limits.git" "C:\si_test_limits"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to clone the repo. Check network connection.
        pause
        exit /b 1
    )

    :: Set files to read-only
    attrib +R "C:\si_test_limits\*.json" /S >nul 2>&1

    echo [OK] Golden limits repo cloned successfully.
)

echo.
echo ============================================
echo   Update Complete!
echo ============================================
echo.
echo   Golden limits location: C:\si_test_limits
echo   Files are set to READ-ONLY.
echo.
echo   You can now run TestScope_local.exe to
echo   check test sequences offline.
echo ============================================
pause
