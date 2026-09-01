@echo off
chcp 65001 >nul
rem ============================================================
rem  Textbook to txt converter (Windows drag & drop tool)
rem  Usage: drag PDF / EPUB files onto this .bat file
rem    - text-based PDF  -> extract text directly
rem    - scanned PDF     -> try OCR (needs Tesseract + chi_sim)
rem    - EPUB            -> extract content
rem  Output: same-name .txt (UTF-8) next to the source file
rem ============================================================

if "%~1"=="" goto :usage

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%..\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" goto :no_venv

echo.
echo  ================================================
echo  Textbook Converter
echo  ================================================

:next_file
if "%~1"=="" goto :done
set "SRC=%~1"
set "EXT=%~x1"
echo.
echo  [Process] %~nx1

if /I "%EXT%"==".pdf" (
    call "%VENV_PY%" "%SCRIPT_DIR%convert_pdf.py" "%SRC%"
    if errorlevel 1 (
        echo.
        echo  [Warn] Text extraction failed, trying OCR...
        call "%VENV_PY%" "%SCRIPT_DIR%convert_pdf_ocr.py" "%SRC%"
    )
) else if /I "%EXT%"==".epub" (
    call "%VENV_PY%" "%SCRIPT_DIR%convert_epub.py" "%SRC%"
) else (
    echo  [Skip] Unsupported format: %EXT%
)
shift
goto :next_file

:done
echo.
echo  ================================================
echo  Done! Output: same-name .txt next to source.
echo  Upload the .txt via the web Upload page.
echo  ================================================
pause
exit /b 0

:usage
echo.
echo  [Hint] Drag PDF or EPUB files onto this window.
echo  You can also drop files into this folder and run this bat.
pause
exit /b 0

:no_venv
echo.
echo  [Error] Python venv not found: %VENV_PY%
echo  Create the venv first (see project README).
pause
exit /b 1