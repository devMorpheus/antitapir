@echo off
chcp 65001 >nul

set "APP_NAME=sing-box.exe"
set "APP_PATH=%~dp0%APP_NAME%"

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ОШИБКА] Запустите скрипт от имени администратора!
    pause
    exit /b 1
)

if not exist "%APP_PATH%" (
    echo [ОШИБКА] Файл не найден: %APP_PATH%
    pause
    exit /b 1
)

netsh advfirewall firewall delete rule name=all program="%APP_PATH%"

netsh advfirewall firewall add rule ^
    name="Anti-Tapir - Inbound"     ^
    dir=in                          ^
    action=allow                    ^
    program="%APP_PATH%"            ^
    enable=yes                      ^
    profile=any

if %errorLevel% neq 0 (
    echo [ОШИБКА] Не удалось добавить правило для входящих подключений
    pause
    exit /b 1
)
echo Входящие подключения разрешены



netsh advfirewall firewall add rule ^
    name="Anti-Tapir - Outbound"    ^
    dir=out                         ^
    action=allow                    ^
    program="%APP_PATH%"            ^
    enable=yes                      ^
    profile=any

if %errorLevel% neq 0 (
    echo [ОШИБКА] Не удалось добавить правило для исходящих подключений
    pause
    exit /b 1
)
echo Исходящие подключения разрешены

echo Правила успешно добавлены в брандмауэр
pause