python -m nuitka    ^
  --standalone      ^
  --follow-imports  ^
  --output-dir=dist ^
  src/antitapir.py

set OUT=out

if exist "%OUT%" (
    rd /s /q "%OUT%"
)

mkdir "%OUT%"

xcopy "dist\antitapir.dist" "%OUT%\antitapir\" /e /i /q
xcopy "src\templates" "%OUT%\templates\" /e /i /q
copy "src\*.bat" "%OUT%\"
copy "src\settings.ini" "%OUT%\"
copy "third-party\sing-box\sing-box.exe" "%OUT%\"
