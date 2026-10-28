"""Keep recording games out of sight (Sam, 2026-10-28: "I dont even need to notice them"): every visible
RelicCardinal window is moved off-screen past the left edge of the virtual desktop, loses its taskbar button, and if
one takes the foreground the window that had it before gets it back. Windowed mode only (record_batch sets
windowmode 2 for parallel runs); a full-screen game cannot be moved.

GameHider(pids=None).start() runs it as a daemon thread inside record_batch; pids=None hides every RelicCardinal
window, a set limits it to those processes. Standalone: python -X utf8 hide_games.py [--seconds N] [--show].
"""
import argparse, ctypes, threading, time
import ctypes.wintypes as wt

import psutil

user32 = ctypes.WinDLL('user32', use_last_error=True)
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = (EnumProc, wt.LPARAM)
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
user32.IsWindowVisible.argtypes = (wt.HWND,)
user32.GetWindowTextLengthW.argtypes = (wt.HWND,)
user32.GetWindowRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
user32.SetWindowPos.argtypes = (wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT)
user32.GetWindowLongPtrW.argtypes = (wt.HWND, ctypes.c_int)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_ssize_t)
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetForegroundWindow.argtypes = (wt.HWND,)
user32.IsWindow.argtypes = (wt.HWND,)
user32.ShowWindow.argtypes = (wt.HWND, ctypes.c_int)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x80, 0x40000
SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x4, 0x10, 0x20
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
GAME = 'reliccardinal.exe'


def window_pid(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def game_pids():
    return {p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == GAME}


def game_windows(pids):
    found = []

    def cb(hwnd, _):
        if window_pid(hwnd) in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found


def offscreen_x(width):
    return user32.GetSystemMetrics(SM_XVIRTUALSCREEN) - width - 200


SIZE = (640, 360)  # the windowed game renders at its window size: 2560x1440 kept two games at 99% GPU, this at 28%


def tuck(hwnd):
    """Small, off-screen and off the taskbar; True when it had to move."""
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = SIZE
    x, y = offscreen_x(w), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    moved = False
    if not ex & WS_EX_TOOLWINDOW or ex & WS_EX_APPWINDOW:  # the taskbar re-reads the style only while hidden
        user32.ShowWindow(hwnd, SW_HIDE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        moved = True
    if (r.left, r.top, r.right - r.left, r.bottom - r.top) != (x, y, w, h):
        user32.SetWindowPos(hwnd, None, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        moved = True
    return moved


def show(hwnd):
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.ShowWindow(hwnd, SW_HIDE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_TOOLWINDOW | WS_EX_APPWINDOW)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    user32.SetWindowPos(hwnd, None, 100, 100, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


class GameHider(threading.Thread):
    def __init__(self, pids=None, interval=0.25, log=print):
        super().__init__(daemon=True)
        self.pids, self.interval, self.log = pids, interval, log
        self.stop = threading.Event()
        self.last_other = None  # the latest foreground window that is not a game

    def run(self):
        seen, refresh = set(), 0.0
        pids = set()
        while not self.stop.is_set():
            if self.pids is not None:
                pids = set(self.pids)
            elif time.time() >= refresh:
                pids, refresh = game_pids(), time.time() + 2
            fg = user32.GetForegroundWindow()
            if fg and window_pid(fg) not in pids:
                self.last_other = fg
            for hwnd in game_windows(pids):
                if tuck(hwnd) and hwnd not in seen:
                    seen.add(hwnd)
                    self.log(f'[hide_games] tucked game window {hwnd} (pid {window_pid(hwnd)})')
            if fg and window_pid(fg) in pids and self.last_other and user32.IsWindow(self.last_other):
                user32.SetForegroundWindow(self.last_other)  # hand focus back to what Sam was using
            self.stop.wait(self.interval)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=float, default=3600)
    ap.add_argument('--show', action='store_true', help='bring every game window back on screen and exit')
    args = ap.parse_args()
    if args.show:
        for hwnd in game_windows(game_pids()):
            show(hwnd)
        return
    hider = GameHider()
    hider.start()
    time.sleep(args.seconds)


if __name__ == '__main__':
    main()
