###############################################################################
# refresher.py — RefreshBrowser
# Encuentra ventanas de navegador y envía F5.
###############################################################################

import time
import ctypes
import win32gui
import win32process
import win32con
import psutil

BROWSERS = {
    "Google Chrome":   "chrome.exe",
    "Microsoft Edge":  "msedge.exe",
    "Mozilla Firefox": "firefox.exe",
    "Brave":           "brave.exe",
}

VK_F5          = 0x74
VK_ALT         = 0x12
KEYEVENTF_KEYUP = 0x0002


def get_target_pids(process_names):
    """PIDs cuyos procesos coinciden con los nombres dados."""
    wanted = {n.lower() for n in process_names}
    pids = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if name and name.lower() in wanted:
                pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def get_windows_for_pids(pids):
    """Handles de ventanas visibles (con título) de esos PIDs."""
    handles = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if not win32gui.GetWindowText(hwnd):
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in pids:
            handles.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return handles


def _press_f5():
    ctypes.windll.user32.keybd_event(VK_F5, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_F5, 0, KEYEVENTF_KEYUP, 0)


def _force_foreground(hwnd):
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        ctypes.windll.user32.keybd_event(VK_ALT, 0, 0, 0)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        ctypes.windll.user32.keybd_event(VK_ALT, 0, KEYEVENTF_KEYUP, 0)


def refresh_browsers(process_names, log):
    """Refresca todas las ventanas de los navegadores indicados."""
    if not process_names:
        log("Sin navegadores seleccionados.")
        return

    pids = get_target_pids(process_names)
    if not pids:
        log("Sin ventanas abiertas de los navegadores seleccionados.")
        return

    handles = get_windows_for_pids(pids)
    count = 0
    for hwnd in handles:
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            _force_foreground(hwnd)
            time.sleep(0.25)
            _press_f5()
            time.sleep(0.15)
            count += 1
        except Exception:
            continue

    log(f"Refrescadas {count} ventana(s).")
