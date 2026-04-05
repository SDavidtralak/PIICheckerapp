@echo off
REM ============================================================
REM CheckPII — Database Backup Script
REM Run this BEFORE starting any spider session.
REM Saves a timestamped .sql backup to CheckPII_Scraper\backups\
REM
REM Usage:
REM   backup_db.bat          (manual backup)
REM   backup_db.bat auto     (called automatically by run_all_spiders.bat)
REM ============================================================

set BACKUP_DIR=C:\Users\David\Desktop\CheckPII_Scraper\backups
set MYSQL_USER=root
set MYSQL_PASS=evopaln12
set DB_NAME=checkpii

REM Create backups folder if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Generate timestamp for filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DATETIME=%%I
set TIMESTAMP=%DATETIME:~0,4%-%DATETIME:~4,2%-%DATETIME:~6,2%_%DATETIME:~8,2%%DATETIME:~10,2%%DATETIME:~12,2%

set BACKUP_FILE=%BACKUP_DIR%\checkpii_%TIMESTAMP%.sql

echo.
echo ===================================================
echo  CheckPII Database Backup
echo  File: checkpii_%TIMESTAMP%.sql
echo  Dir:  %BACKUP_DIR%
echo ===================================================
echo.
echo Backing up database...

mysqldump -u %MYSQL_USER% -p%MYSQL_PASS% %DB_NAME% > "%BACKUP_FILE%"

if %ERRORLEVEL% == 0 (
    echo.
    echo ✓ Backup successful: checkpii_%TIMESTAMP%.sql
    echo.
) else (
    echo.
    echo ✗ Backup FAILED — check MySQL is running and password is correct.
    echo   Edit backup_db.bat and set MYSQL_PASS to your MySQL root password.
    echo.
    if "%1"=="auto" (
        echo ⚠ Spiders will NOT start without a successful backup.
        echo ⚠ Fix the backup issue first, then run again.
        pause
        exit /b 1
    )
)

REM Keep only the 10 most recent backups to save disk space
echo Cleaning up old backups (keeping 10 most recent)...
for /f "skip=10 delims=" %%F in ('dir /b /o-d "%BACKUP_DIR%\*.sql"') do (
    del "%BACKUP_DIR%\%%F"
    echo   Deleted old backup: %%F
)

echo Done.
if not "%1"=="auto" pause
