# Anti-Tapir

### Как собрать:
1. Перед началом у вас должен быть config.json для sing-box, в котором настроен тунель TUN (можно получить из ThroneVPN)
2. Закинуть config.json в папку key
3. Выполнить скрипт genkey.py для создания ключа
4. Выполнить скрипт genconfig.py для шифрования и упаковки конфига в нужный формат
5. Файл key.py скопировать в src/
6. Выполнить build_singbox.bat
7. Выполнить build_antitapir.bat
