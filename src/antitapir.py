import cv2
import dxcam
import pywinctl
import time
import subprocess
import os

import ctypes
import ctypes.wintypes
import psutil

import configparser
import numpy as np
import argparse
import socket

import sys
import random

import requests

import colorama

from concurrent.futures import ThreadPoolExecutor, as_completed

from key import key

APP_VER="v0.16"

APP_LISTEN_HOST="127.0.0.1"
APP_LISTEN_PORT=7777

SINGBOX_ADDR_HOST="127.0.0.1"
SINGBOX_ADDR_PORT=8888
SINGBOX_ADDR = (SINGBOX_ADDR_HOST, SINGBOX_ADDR_PORT)

ASPECT_16_10 = 1.60
ASPECT_16_9  = 1.78
ASPECT_21_9  = 2.39

config = configparser.ConfigParser()
sock = None

CMD_RUN_PNPUTIL_PATH = "C:\\Windows\\System32\\pnputil.exe"
CMD_RUN_PNPUTIL_ARGS = "/remove-device \"SWD\\Wintun\\{DB374276-5A86-C6F7-EBAD-9D6FFF9AA387}\" /subtree"

CMD_RUN_SINGBOX_PATH = "sing-box.exe"
CMD_RUN_SINGBOX_ARGS = "run -c config.json"

def getRunnedProceesses():
    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    result = result.stdout.lower()
    return result

def killProcesses(game: str, store: str):
    runnedProceesses = getRunnedProceesses()

    tokill = [
        "sing-box.exe"
    ]

    if game == 'destiny2':
        tokill.append('destiny2.exe')
    elif game == 'marathon':
        tokill.append('marathon.exe')

    if store == 'steam' and int(config['Steam']['UseShutdown']) == 0:
        tokill.append('steam.exe')
    elif store == 'epic':
        tokill.append('epicgameslauncher.exe')

    for task in tokill:
        if task in runnedProceesses:
            subprocess.run(["taskkill", "/f", "/im", task])

    if 'steam.exe' in runnedProceesses:
        if int(config['Steam']['UseShutdown']) == 1:
            print('Steam UseShutdown=1')

            runAsUser(config['Steam']['Path'], "-shutdown")

            isDoneCount = 0
            
            print('Ожидание завершения Steam: ', end='')
            sys.stdout.flush()
            while True:
                print('.', end='')
                sys.stdout.flush()

                checkSteam = getRunnedProceesses()

                if ('steam.exe' in checkSteam) == False:
                    print(" успешно")
                    break
                else:
                    isDoneCount += 1

                if isDoneCount == 30:
                    print(" ошибка")
                    sys.exit()
                
                time.sleep(1)

def loadTemplates(game: str, language: str):
    template = {}
    if game == 'destiny2':
        template["connecting"]             = cv2.cvtColor(cv2.imread(f'templates/{game}/{language}/connecting.png'),             cv2.COLOR_RGB2BGR)

    template["signing_in"]                 = cv2.cvtColor(cv2.imread(f'templates/{game}/{language}/signing_in.png'),             cv2.COLOR_RGB2BGR)
    template["checking_for_updates"]       = cv2.cvtColor(cv2.imread(f'templates/{game}/{language}/checking_for_updates.png'),   cv2.COLOR_RGB2BGR)
    template["verifying_content"]          = cv2.cvtColor(cv2.imread(f'templates/{game}/{language}/verifying_content.png'),      cv2.COLOR_RGB2BGR)

    if game == 'marathon':
        template["checking_storage_space"] = cv2.cvtColor(cv2.imread(f'templates/{game}/{language}/checking_storage_space.png'), cv2.COLOR_RGB2BGR)

    return template

def runAsAdmin(path, args, hidden=False):
    if hidden == False:
        result = subprocess.Popen(f"{path} {args}")
    else:
        result = subprocess.Popen(f"{path} {args}", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return result

def runAsUser(path, args="", hidden=False):
    # ── Constants ────────────────────────────────────────────────────────────
    TOKEN_DUPLICATE        = 0x0002
    TOKEN_QUERY            = 0x0008
    TOKEN_ASSIGN_PRIMARY   = 0x0001
    GENERIC_ALL            = 0x10000000
    LOGON_WITH_PROFILE     = 0x00000001
    CREATE_UNICODE_ENV     = 0x00000400
    STARTF_USESHOWWINDOW   = 0x00000001
    SW_HIDE                = 0
    SW_SHOWNORMAL          = 1
    SecurityImpersonation  = 2
    TokenPrimary           = 1

    # ── Structures ───────────────────────────────────────────────────────────
    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb",              ctypes.wintypes.DWORD),
            ("lpReserved",      ctypes.c_wchar_p),
            ("lpDesktop",       ctypes.c_wchar_p),
            ("lpTitle",         ctypes.c_wchar_p),
            ("dwX",             ctypes.wintypes.DWORD),
            ("dwY",             ctypes.wintypes.DWORD),
            ("dwXSize",         ctypes.wintypes.DWORD),
            ("dwYSize",         ctypes.wintypes.DWORD),
            ("dwXCountChars",   ctypes.wintypes.DWORD),
            ("dwYCountChars",   ctypes.wintypes.DWORD),
            ("dwFillAttribute", ctypes.wintypes.DWORD),
            ("dwFlags",         ctypes.wintypes.DWORD),
            ("wShowWindow",     ctypes.wintypes.WORD),
            ("cbReserved2",     ctypes.wintypes.WORD),
            ("lpReserved2",     ctypes.c_void_p),
            ("hStdInput",       ctypes.wintypes.HANDLE),
            ("hStdOutput",      ctypes.wintypes.HANDLE),
            ("hStdError",       ctypes.wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess",    ctypes.wintypes.HANDLE),
            ("hThread",     ctypes.wintypes.HANDLE),
            ("dwProcessId", ctypes.wintypes.DWORD),
            ("dwThreadId",  ctypes.wintypes.DWORD),
        ]

    # ── WinAPI setup ─────────────────────────────────────────────────────────
    kernel32  = ctypes.windll.kernel32
    advapi32  = ctypes.windll.advapi32
    userenv   = ctypes.windll.userenv

    userenv.CreateEnvironmentBlock.restype  = ctypes.wintypes.BOOL
    userenv.DestroyEnvironmentBlock.restype = ctypes.wintypes.BOOL
    advapi32.CreateProcessWithTokenW.restype = ctypes.wintypes.BOOL

    # ── Find explorer.exe (always runs as the real user) ─────────────────────
    explorer_pid = None
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        if proc.info['name'] and proc.info['name'].lower() == 'explorer.exe':
            explorer_pid = proc.info['pid']
            break

    if not explorer_pid:
        raise RuntimeError("explorer.exe not found — is a user logged in?")

    # ── Open explorer process ─────────────────────────────────────────────────
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ           = 0x0010
    hExplorer = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, explorer_pid
    )
    if not hExplorer:
        raise RuntimeError(f"OpenProcess failed: {kernel32.GetLastError()}")

    # ── Get and duplicate the user token ─────────────────────────────────────
    hToken = ctypes.wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        hExplorer,
        TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY,
        ctypes.byref(hToken)
    ):
        kernel32.CloseHandle(hExplorer)
        raise RuntimeError(f"OpenProcessToken failed: {kernel32.GetLastError()}")

    hPrimaryToken = ctypes.wintypes.HANDLE()
    if not advapi32.DuplicateTokenEx(
        hToken,
        GENERIC_ALL,
        None,
        SecurityImpersonation,  # ImpersonationLevel
        TokenPrimary,           # TokenType — required for CreateProcessWithTokenW
        ctypes.byref(hPrimaryToken)
    ):
        kernel32.CloseHandle(hToken)
        kernel32.CloseHandle(hExplorer)
        raise RuntimeError(f"DuplicateTokenEx failed: {kernel32.GetLastError()}")

    # ── Build environment block from the user token ───────────────────────────
    # Critical: inherit user env vars (PATH, APPDATA, etc.), not the admin ones
    lpEnvironment = ctypes.c_void_p()
    if not userenv.CreateEnvironmentBlock(
        ctypes.byref(lpEnvironment), hPrimaryToken, False
    ):
        kernel32.CloseHandle(hPrimaryToken)
        kernel32.CloseHandle(hToken)
        kernel32.CloseHandle(hExplorer)
        raise RuntimeError(f"CreateEnvironmentBlock failed: {kernel32.GetLastError()}")

    # ── Configure startup info ────────────────────────────────────────────────
    si = STARTUPINFOW()
    si.cb        = ctypes.sizeof(STARTUPINFOW)
    si.lpDesktop = "winsta0\\default"   # required — attach to interactive desktop
    si.dwFlags   = STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE if hidden else SW_SHOWNORMAL

    pi = PROCESS_INFORMATION()

    # Build command line — quote the path in case it has spaces
    clean_path = path.strip('"')
    cmd = f'"{clean_path}"'
    if args:
        cmd += f' {args}'

    working_dir = os.path.dirname(os.path.abspath(clean_path))

    # ── Launch ────────────────────────────────────────────────────────────────
    success = advapi32.CreateProcessWithTokenW(
        hPrimaryToken,          # hToken
        LOGON_WITH_PROFILE,     # dwLogonFlags — loads the user profile
        None,                   # lpApplicationName
        cmd,                    # lpCommandLine
        CREATE_UNICODE_ENV,     # dwCreationFlags
        lpEnvironment,          # lpEnvironment (user env block)
        working_dir,            # lpCurrentDirectory
        ctypes.byref(si),       # lpStartupInfo
        ctypes.byref(pi)        # lpProcessInformation
    )

    # ── Cleanup ───────────────────────────────────────────────────────────────
    userenv.DestroyEnvironmentBlock(lpEnvironment)
    kernel32.CloseHandle(hPrimaryToken)
    kernel32.CloseHandle(hToken)
    kernel32.CloseHandle(hExplorer)

    if not success:
        raise RuntimeError(
            f"CreateProcessWithTokenW failed: {kernel32.GetLastError()}\n"
            f"  path='{path}'\n"
            f"  cmd='{cmd}'"
        )

    kernel32.CloseHandle(pi.hThread)  # we don't need the thread handle
    return pi.hProcess  # caller is responsible for closing this

def code(data, pos):
    out = bytearray()
    index = pos
    for element in data:
        enc = element ^ key[index]
        out.append(enc)
        if index == 255:
            index = 0
        else:
            index = (index + 1) % 256

    return out

def encode(data):
    pos = random.randint(0, 255)
    out = code(data, pos)
    out.append(pos)
    return out

def decode(data):
    pos = data[len(data) - 1]
    data = data[:-1]
    out = code(data, pos)
    return out

def checkExternalIP(target):
    try:
        target_ip = socket.gethostbyname(target)
        response = requests.get("https://ipinfo.io/json", timeout=5)
        response.raise_for_status()
        current_ip = response.json().get("ip", "")
        return current_ip == target_ip
    except Exception as e:
            print(f"\nНеудача {e} ")
            return False

def cleanup():
    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    result = result.stdout.lower()

    tokill = [
        "sing-box.exe"
    ]

    for task in tokill:
        if task in result:
            subprocess.run(["taskkill", "/f", "/im", task])

executor = None
scales = None
resized_templates_cache = {}

def initCapture(threads):
    global executor, scales
    scales = np.linspace(
        float(config['Capture']['MinSize']),
        float(config['Capture']['MaxSize']),
        int(config['Capture']['DetectSteps'])
    )
    executor = ThreadPoolExecutor(max_workers=threads)

def precomputeTemplates(template):
    global resized_templates_cache
    cache_key = id(template)
    if cache_key not in resized_templates_cache:
        resized_map = {}
        for key, value in template.items():
            resized_map[key] = [
                (scale, cv2.resize(value, None, fx=scale, fy=scale, 
                                   interpolation=cv2.INTER_LINEAR))
                for scale in scales
            ]
        resized_templates_cache[cache_key] = resized_map
    return resized_templates_cache[cache_key]

def captureMatch(image, template, threads):
    global executor, scales
    
    if executor is None:
        initCapture(threads)
    
    detect_level = float(config['Capture']['DetectLevel'])
    img_h, img_w = image.shape[:2]
    
    resized_map = precomputeTemplates(template)
    
    result_found = [None]
    num_threads = min(threads, len(scales))
    
    items = list(resized_map.items())
    chunks = [items[i::num_threads] for i in range(min(num_threads, len(items)))]

    def search_chunk(chunk):
        for key, scale_variants in chunk:
            for scale, resized in scale_variants:
                if result_found[0] is not None:
                    return None
                if resized.shape[0] > img_h or resized.shape[1] > img_w:
                    continue
                result = cv2.matchTemplate(image, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > detect_level:
                    return key
        return None

    futures = {executor.submit(search_chunk, chunk) : chunk for chunk in chunks}
    
    for future in as_completed(futures):
        res = future.result()
        if res is not None:
            result_found[0] = res
            for f in futures:
                f.cancel()
            return res
    
    return None

def calcOffset(window, label_start_x, label_start_y, label_width, label_height):
    clientFrame  = window.getClientFrame()
    clientWidth  = (clientFrame.right  - clientFrame.left)
    clientHeight = (clientFrame.bottom - clientFrame.top)

    rect_start_x = int(clientFrame.left + (clientWidth  * label_start_x))
    rect_start_y = int(clientFrame.top  + (clientHeight * label_start_y))
    rect_end_x   = int(rect_start_x     + (clientWidth  * label_width))
    rect_end_y   = int(rect_start_y     + (clientHeight * label_height))

    return (rect_start_x, rect_start_y, rect_end_x, rect_end_y)

def main(game: str, store: str, language: str, exitdelay: float, threads: int, customcapture: bool,showcapture: bool):
    global config
    global sock

    if game != "destiny2" and game != "marathon":
        print(f"Игра \"{game}\" не поддерживается")
        sys.exit()

    if store != "steam" and store != "epic":
        print(f"Магазин \"{store}\" не поддерживается")
        sys.exit()
    
    if game == "marathon" and store == "epic":
        print(f"Marathon и EGS не поддерживается")
        sys.exit()

    if language != 'ru' and language != 'en':
        print(f"Язык - ru либо en")
        sys.exit()
    
    if exitdelay < 0 or exitdelay > 10:
        print(f"Неккоректное заначение задержки")
        sys.exit()

    if threads < 0 or threads > 32:
        print(f"Неккоректное заначение потоков")
        sys.exit()

    if ctypes.windll.shell32.IsUserAnAdmin() == False:
        print("Запустите программу от имени Администратора")
        sys.exit()
        
    print(f"Игра: {game}, магазин: {store}, язык: {language}")

    configReadResult = config.read(f"settings.ini")

    if len(configReadResult) == 0:
        print("Невозможно прочитать файл настроек settings.ini")
        sys.exit()

    template = loadTemplates(game, language)

    killProcesses(game, store)

    runAsAdmin(CMD_RUN_PNPUTIL_PATH, CMD_RUN_PNPUTIL_ARGS, True)
    time.sleep(0.5)

    startTime = time.time()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(15)
    sock.bind((APP_LISTEN_HOST, APP_LISTEN_PORT))

    if bool(int(config['TapirBox']['ShowLogs'])) == True:
        runAsAdmin(CMD_RUN_SINGBOX_PATH, CMD_RUN_SINGBOX_ARGS, False)
    else:
        runAsAdmin(CMD_RUN_SINGBOX_PATH, CMD_RUN_SINGBOX_ARGS, True)

    time.sleep(0.5)
    
    print("Запуск VPN: ", end='')
    sys.stdout.flush()
    
    while True:
        data, _ = sock.recvfrom(6)
        payload = decode(data)
        if payload.decode('utf-8') == "hello":
            print("успешно")
            sock.sendto(encode("hello".encode('utf-8')), SINGBOX_ADDR)
            break
        else:
            print("ошибка")
            sys.exit(1)

    if int(config['TapirBox']['SkipCheckIP']) == 0:
        print("Подключение: ", end='')
        sys.stdout.flush()
        isConnectedCount = 0
        while True:
            print('.', end='')
            sys.stdout.flush()

            isConnected = checkExternalIP("antitapir.ru")

            if isConnected == True:
                print(" успешно")
                break
            else:
                isConnectedCount += 1

            if isConnectedCount == 10:
                print(" ошибка")
                sys.exit()

            time.sleep(1)
    else:
        print("SkipCheckIP=1")

    if store == 'steam':
        if game == 'destiny2':    
            print("Запуск Steam и Destiny 2")
            runAsUser(config['Steam']['Path'], "-applaunch 1085660")
        elif game == 'marathon':
            print("Запуск Steam и Marathon")
            runAsUser(config['Steam']['Path'], "-applaunch 3065800")
    elif store == 'epic':
        if game == 'destiny2':    
            print("Запуск Epic")
            runAsUser(config['Epic']['Path'], "")

            time.sleep(7)

            print("Запуск Destiny 2")
            runAsUser(config['Epic']['Path'], "-com.epicgames.launcher://apps/592c359fb0e0413fb46dee2d24448eb4?action=launch")

    targetTitle = ''
    if game == 'destiny2':
        print("Ожидание окна Destiny 2: ", end='')
        targetTitle = "Destiny 2"
    elif game == 'marathon':
        print("Ожидание окна Marathon: ", end='')
        targetTitle = "Marathon"
        
    window = None
    while True:
        target = pywinctl.getWindowsWithTitle(targetTitle)

        if target:
            window = target[0]
            exe = window.getAppName()
            if exe == 'destiny2.exe' or exe =='Marathon.exe':
                break
        
        elapsed = time.time() - startTime
    
        if elapsed > 200:
            print(" таймаут")
            sys.exit()
            break

        time.sleep(0.1)

    clientFrame = window.getClientFrame()
    clientWidth = (clientFrame.right  - clientFrame.left)
    clientHeight = (clientFrame.bottom - clientFrame.top)

    print(f" {clientFrame}")

    aspect_ratio = round(clientWidth / clientHeight, 2)

    label_start_x, label_start_y, label_width, label_height = 0, 0, 0, 0

    if (ASPECT_16_10 * 0.95) < aspect_ratio < (ASPECT_16_10 * 1.05):
        print("Соотношение сторон: 16:10")
        label_start_x = 0.61
        label_start_y = 0.71
        label_width   = 0.163
        label_height  = 0.05
    elif (ASPECT_16_9 * 0.95) < aspect_ratio < (ASPECT_16_9 * 1.05):
        print("Соотношение сторон: 16:9")
        label_start_x = 0.625
        label_start_y = 0.736
        label_width   = 0.15
        label_height  = 0.05
    elif (ASPECT_21_9 * 0.95) < aspect_ratio < (ASPECT_21_9 * 1.05):
        print("Соотношение сторон: 21:9")
        label_start_x = 0.595
        label_start_y = 0.735
        label_width   = 0.11
        label_height  = 0.05
    else:
        print("Неподдерживаемое соотношение сторон")
        if customcapture == False:
            print("Настройте свои параметры захвата [CustomCapture] в файле settings.ini)")
            print("Чтобы включить кастомный захват используйте флаг запуска --customcapture")
            print("Для отладки используйте флаг запуска --showcapture")
            sys.exit()

    if customcapture == True:
        print("Включен CustomCapture!")
        label_start_x = int(config['CustomCapture']['StartX'])
        label_start_y = int(config['CustomCapture']['StartY'])
        label_width   = int(config['CustomCapture']['Width'])
        label_height  = int(config['CustomCapture']['Height'])
    
    # setup capture
    print(dxcam.device_info())
    print(dxcam.output_info())
    
    camera = dxcam.create(
        backend="dxgi",
        processor_backend="cv2",
        output_color="BGR"
    )

    left, top, right, bottom = 0, 0, 0, 0

    color_search  = (37, 106, 244)
    color_founded = (0, 255, 0)

    color = None

    old_state = -1
    new_state = -1

    while True:
        (newLeft, newTop, newRight, newBottom) = calcOffset(window, label_start_x, label_start_y, label_width, label_height)

        if newLeft != left or newTop != top or newRight != right or newBottom != bottom:
            if camera.is_capturing:
                camera.stop()

            left   = newLeft
            top    = newTop
            right  = newRight
            bottom = newBottom

            if left == 0 and top == 0 and right == 0 and bottom == 0:
                print("Ошибка захвата окна")
                break

            if left < 0 or top < 0:
                continue

            if right > camera.width or bottom > camera.height:
                continue

            camera.start(region=(left, top, right, bottom), target_fps = 100)

        image = camera.get_latest_frame()
        imageWidth = right - left
        imageHeight = bottom - top

        if image is None:
            continue

        target = captureMatch(image, template, threads)

        match(target):
            case "connecting":
                new_state = 1
                color = color_founded

            case "signing_in":
                new_state = 2
                color = color_founded

            case "checking_for_updates":
                new_state = 3
                color = color_founded

            case "verifying_content":
                new_state = 4
                color = color_founded

            case "checking_storage_space":
                new_state = 5
                color = color_founded

            case _:
                new_state = 0
                color = color_search

        if (old_state == 3 or old_state == 4 or old_state == 5) and new_state == 0:
            print("State change exit")
            break
        
        elapsed = time.time() - startTime
        
        if new_state != old_state:
            old_state = new_state
            print(f"[{elapsed:.3f}] State change {new_state} - {target.replace("_", " ") if target else "null" }")
        
        if showcapture:
            cv2.rectangle(image, (2, 2), (imageWidth - 2, imageHeight - 2), color, 2)

            #scale = 2
            #h, w = image.shape[:2]
            #upscaled = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_LINEAR)

            cv2.imshow("Anti-Tapir", image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
    
        if elapsed > 200:
            print("Таймаут")
            sys.exit()
            break

    time.sleep(exitdelay)
    #sock.sendto(encode("end".encode('utf-8')), SINGBOX_ADDR)
    camera.stop()
    print("Выход")

colorama.init(autoreset=True, strip=False, convert=True)

print(f"========== Anti-Tapir {APP_VER} by Морфеус & SilkEmbraces =========")
print( "| Офицальные релизы публикуются только на следующих ресурсах: |")
print( "|   GitHub  : https://github.com/devMorpheus/antitapir        |")
print( "|   Discord : https://discord.gg/d2dust                       |")
print( "| Сборки, полученные из других источников нами не проверяются |")
print( "|         и могут быть модифицированы третьими лицами         |")
print( "|                используйте их на свой риск                  |")
print( "|     Всегда проверяйте контрольные суммы после загрузки      |")
print( "===============================================================")

parser = argparse.ArgumentParser(description="Anti-Tapir")
parser.add_argument("--game",          type=str,   required=True, help="Игра: destiny2, marathon")
parser.add_argument("--store",         type=str,   required=True, help="Магазин: steam, epic")
parser.add_argument("--language",      type=str,   required=True, help="Язык: ru, en")
parser.add_argument("--exitdelay",     type=float, required=True, help="Задержка перед выходом (секунды)")
parser.add_argument("--threads",       type=int,   required=True, help="Потоков процессора для обработки захвата изображения")
parser.add_argument("--customcapture", action='store_true',       help="Использовать кастомные параметры захвата изображения")
parser.add_argument("--showcapture",   action='store_true',       help="Показывать процесс захвата изображения")
args = parser.parse_args()

try:
    main(args.game, args.store, args.language, args.exitdelay, args.threads, args.customcapture, args.showcapture)
finally:
    cleanup()

    if sock:
        sock.sendto(encode("end".encode('utf-8')), SINGBOX_ADDR)