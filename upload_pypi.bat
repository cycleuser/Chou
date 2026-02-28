@echo off
REM Chou - Upload to PyPI
REM Usage: upload_pypi.bat [--test]

setlocal enabledelayedexpansion

echo === Chou PyPI Upload Script ===

REM Get version from __version__.py
for /f "tokens=*" %%i in ('python -c "from chou.__version__ import __version__; print(__version__)"') do set VERSION=%%i
echo Version: %VERSION%

REM Check for --test flag
if "%1"=="--test" (
    set REPO=testpypi
    echo Uploading to TestPyPI
) else (
    set REPO=pypi
    echo Uploading to PyPI
)

REM Clean previous builds
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.egg-info rmdir /s /q *.egg-info
if exist chou.egg-info rmdir /s /q chou.egg-info

REM Build the package
echo Building package...
python -m pip install --upgrade build twine -q
python -m build
if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

REM Check the distribution
echo Checking distribution...
python -m twine check dist/*
if errorlevel 1 (
    echo Distribution check failed!
    exit /b 1
)

REM Upload to PyPI
echo Uploading to %REPO%...
if "%REPO%"=="testpypi" (
    python -m twine upload --repository testpypi dist/*
) else (
    python -m twine upload dist/*
)

if errorlevel 1 (
    echo Upload failed!
    exit /b 1
)

echo Done! Chou v%VERSION% uploaded to %REPO%
echo Install with: pip install chou

endlocal
