@echo off
setlocal enabledelayedexpansion

set ADB_PATH="C:\Users\Dell\AppData\Local\Android\Sdk\platform-tools\adb.exe"

if exist output.apks (
    echo Da tim thay output.apks, bo qua buoc build, cai luon...
) else (
    echo Dang tim file .aab...

    set AAB_FILE=
    for %%f in (*.aab) do if not defined AAB_FILE set "AAB_FILE=%%f"

    if not defined AAB_FILE (
        echo Khong tim thay file .aab trong folder nay!
        pause
        exit /b 1
    )

    echo Dang build tu file: !AAB_FILE!
    java -jar bundletool.jar build-apks --bundle="!AAB_FILE!" --output=output.apks --local-testing

    if errorlevel 1 (
        echo Build that bai!
        pause
        exit /b 1
    )
)

echo Dang cai len thiet bi...
java -jar bundletool.jar install-apks --apks=output.apks --adb=%ADB_PATH%

if errorlevel 1 (
    echo Cai dat that bai!
) else (
    echo.
    echo ================================
    echo   CAI DAT THANH CONG!
    echo ================================
    echo.
)

pause