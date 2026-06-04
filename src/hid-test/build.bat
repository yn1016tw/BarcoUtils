@echo off
REM Build hid_test.cpp with MSVC
REM Tries vcvars64.bat automatically; works with VS 2017/2019/2022 BuildTools.

setlocal
set SRC=%~dp0hid_test.cpp
set OUT=%~dp0hid_test.exe

REM ---- locate vcvars64.bat (first match wins) ----
set VCVARS=
for %%V in (2022 2019 2017) do (
    for %%E in (Community Professional Enterprise BuildTools) do (
        if exist "C:\Program Files\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat" (
            if not defined VCVARS set "VCVARS=C:\Program Files\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat"
        )
        if exist "C:\Program Files (x86)\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat" (
            if not defined VCVARS set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat"
        )
    )
)

if not defined VCVARS (
    echo [WARN] vcvars64.bat not found, trying cl.exe from PATH...
    goto :build
)
echo Using: %VCVARS%
call "%VCVARS%" >nul 2>&1

:build
echo Building %SRC% ...

cl.exe /nologo /W3 /O2 /EHsc /MT ^
    /D_UNICODE /DUNICODE /D_CRT_SECURE_NO_WARNINGS ^
    "%SRC%" ^
    /Fe:"%OUT%" ^
    /link /INCREMENTAL:NO setupapi.lib hid.lib kernel32.lib

if %ERRORLEVEL% neq 0 (
    echo.
    echo [FAIL] Build failed.
    exit /b 1
)

echo.
echo [OK] Built: %OUT%
echo Run:  %OUT%
endlocal
