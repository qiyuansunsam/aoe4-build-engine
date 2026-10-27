"""Find which configuration_system.lua windowmode value gives a real window: launch the game to its menu with the
value and 960x540, wait for its window, read the window style, rectangle and the display mode, close the game and
restore the player's configuration. Usage: python -X utf8 probe_windowmode.py 2 [1 ...]
"""
import ctypes, ctypes.wintypes as wt, os, re, shutil, subprocess, sys, time, winreg
from pathlib import Path

USER_DIR = Path(os.environ['USERPROFILE']) / 'Documents' / 'My Games' / 'Age of Empires IV'
CONFIG = USER_DIR / 'configuration_system.lua'
BACKUP = USER_DIR / 'configuration_system.lua.probe-backup'
APP_ID = '1466860'
user32 = ctypes.windll.user32


def steam_exe():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
        return winreg.QueryValueEx(key, 'SteamExe')[0]


def game_pid():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RelicCardinal.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower() == 'reliccardinal.exe':
            return int(parts[1])
    return None


def set_values(text, values):
    def sub(m):
        return m[1] + values[m[2]] + m[4] if m[2] in values else m[0]
    return re.sub(r'(setting = "(\w+)",\s*\n\s*variant\w+ = )([^,\r\n]+)(,)', sub, text)


def read_value(text, key):
    m = re.search(r'setting = "%s",\s*\n\s*variant\w+ = ([^,\r\n]+),' % key, text)
    return m.group(1) if m else None


def windows_of(pid):
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return found


def display_mode():
    class DEVMODE(ctypes.Structure):
        _fields_ = [('dmDeviceName', wt.WCHAR * 32), ('dmSpecVersion', wt.WORD), ('dmDriverVersion', wt.WORD), ('dmSize', wt.WORD), ('dmDriverExtra', wt.WORD), ('dmFields', wt.DWORD), ('pad', ctypes.c_byte * 68), ('dmPelsWidth', wt.DWORD), ('dmPelsHeight', wt.DWORD), ('rest', ctypes.c_byte * 40)]
    dm = DEVMODE(); dm.dmSize = ctypes.sizeof(DEVMODE)
    user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    return dm.dmPelsWidth, dm.dmPelsHeight


def probe(value):
    original = CONFIG.read_text(encoding='utf-8')
    shutil.copyfile(CONFIG, BACKUP)
    CONFIG.write_text(set_values(original, {'windowmode': value, 'resolution': '"960:540:0:0"', 'mastervolume': '0.00000', 'verticalsync': 'false'}), encoding='utf-8')
    before = display_mode()
    result = {'value': value, 'displayBefore': before}
    try:
        subprocess.Popen([steam_exe(), '-applaunch', APP_ID, '-dev'])
        pid = None
        deadline = time.time() + 120
        while time.time() < deadline and pid is None:
            pid = game_pid(); time.sleep(1)
        result['pid'] = pid
        if pid:
            t0 = time.time(); samples = []
            while time.time() - t0 < 75:
                for hwnd in windows_of(pid):
                    style = user32.GetWindowLongW(hwnd, -16); ex = user32.GetWindowLongW(hwnd, -20)
                    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
                    title = ctypes.create_unicode_buffer(256); user32.GetWindowTextW(hwnd, title, 256)
                    samples.append({'t': round(time.time() - t0), 'title': title.value, 'style': hex(style & 0xffffffff), 'caption': bool(style & 0x00C00000), 'thickframe': bool(style & 0x00040000), 'popup': bool(style & 0x80000000), 'rect': [r.left, r.top, r.right, r.bottom], 'display': display_mode()})
                time.sleep(5)
            result['samples'] = samples[-4:]
            result['writtenBack'] = read_value(CONFIG.read_text(encoding='utf-8'), 'windowmode')
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
            time.sleep(4)
    finally:
        os.replace(BACKUP, CONFIG)
        result['displayAfter'] = display_mode()
        result['restored'] = read_value(CONFIG.read_text(encoding='utf-8'), 'windowmode')
    return result


if __name__ == '__main__':
    import json
    for v in sys.argv[1:] or ['2']:
        print(json.dumps(probe(v)), flush=True)
        time.sleep(5)
