@echo off

cd /d "%~dp0"

cd third-party/sing-box

REM go build -tags "with_utls" -ldflags "-s -w -H windowsgui" ./cmd/sing-box

go build -tags "with_utls" -ldflags "-s -w" ./cmd/sing-box

copy sing-box.exe ..\..\src\

pause