# -*- coding: utf-8 -*-
"""
ابزارهای سیستمی ویندوز:
- مدیریت مسیرهای پروژه ساختاریافته (assets/fonts, assets/icons, assets/sounds, data)
- پخش و توقف فایل‌های صوتی MP3 آلارم با استفاده از WinMM (mciSendStringW) بدون نیاز به کتابخانه جانبی
- مخفی کردن کامل ویجت از نوار وظیفه (Taskbar) و نمایش فقط در Hidden Icons (System Tray)
- مدیریت Z-Index و عبوردهی کلیک (Click-Through) در حالت قفل
- گرد کردن گوشه‌های پنجره در ویندوز 10 و 11 و بارگذاری فونت‌های فارسی باندل‌شده
"""

import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import sys
import threading

IS_WIN = sys.platform == "win32"

try:
    import winreg
except ImportError:
    winreg = None

if IS_WIN:
    try:
        import win32api
        import win32con
        import win32gui
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
else:
    HAS_WIN32 = False

_linux_audio_proc = None

# ثابت‌های Win32 API
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2

APP_REG_NAME = "PersianClockCalendarWidget"
DEFAULT_ALARM_SOUND = "heeeeyyyyy.mp3"


def get_project_root() -> str:
    """
    دریافت ریشه اصلی پروژه:
    - در حالت فایل اجرایی (.exe): پوشه کنار فایل اجرایی (یا ریشه پروژه اگر داخل release/ باشد)
    - در حالت سورس پایتون: پوشه مادرِ src/
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        parent_dir = os.path.dirname(exe_dir)
        if os.path.basename(exe_dir).lower() == "release" and os.path.isdir(os.path.join(parent_dir, "data")):
            return parent_dir
        return exe_dir
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir() -> str:
    """دریافت مسیر پوشه data/ برای ذخیره تنظیمات، آلارم‌ها و مناسبت‌های شخصی"""
    root = get_project_root()
    data_dir = os.path.join(root, "data")
    try:
        os.makedirs(data_dir, exist_ok=True)
        test_f = os.path.join(data_dir, ".write_test")
        with open(test_f, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_f)
        return data_dir
    except Exception:
        fallback = os.path.join(os.path.expanduser("~"), ".local", "share", "PersianClockWidget", "data")
        os.makedirs(fallback, exist_ok=True)
        return fallback


def get_resource_path(relative_path: str) -> str:
    """دریافت مسیر فایل‌های باندل شده در PyInstaller (_MEIPASS) یا در پوشه پروژه"""
    if hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(p):
            return p
    return os.path.join(get_project_root(), relative_path)


def get_available_alarm_sounds() -> list[str]:
    """
    دریافت لیست فایل‌های صوتی آلارم موجود در assets/sounds
    با قرار دادن heeeeyyyyy.mp3 به عنوان گزینه اول و پیش‌فرض
    """
    sounds_dir = get_resource_path(os.path.join("assets", "sounds"))
    files = []
    if os.path.isdir(sounds_dir):
        for f in sorted(os.listdir(sounds_dir)):
            if f.lower().endswith((".mp3", ".wav")):
                files.append(f)
    if DEFAULT_ALARM_SOUND in files:
        files.remove(DEFAULT_ALARM_SOUND)
        files.insert(0, DEFAULT_ALARM_SOUND)
    elif not files:
        files = [DEFAULT_ALARM_SOUND]
    return files


def play_mp3_sound(sound_filename: str, repeat: bool = True) -> bool:
    """پخش غیرمسدودکننده فایل MP3 (در ویندوز با WinMM و در لینوکس با mpv/ffplay/mpg123/cvlc)"""
    global _linux_audio_proc
    stop_mp3_sound()
    sound_path = get_resource_path(os.path.join("assets", "sounds", sound_filename))
    if not os.path.exists(sound_path):
        # تلاش با صدای پیش‌فرض در صورت یافت نشدن فایل
        sound_path = get_resource_path(os.path.join("assets", "sounds", DEFAULT_ALARM_SOUND))
        if not os.path.exists(sound_path):
            return False

    if not IS_WIN:
        candidates = [
            ["mpv", "--no-video", "--really-quiet"] + (["--loop-file=inf"] if repeat else []) + [sound_path],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"] + (["-loop", "0"] if repeat else []) + [sound_path],
            ["mpg123", "-q"] + (["--loop", "-1"] if repeat else []) + [sound_path],
            ["cvlc", "--play-and-exit", "--quiet"] + (["--loop"] if repeat else []) + [sound_path],
        ]
        for cmd in candidates:
            if shutil.which(cmd[0]):
                try:
                    _linux_audio_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        return False

    try:
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'open "{sound_path}" type mpegvideo alias widget_alarm_audio', None, 0, 0)
        play_cmd = "play widget_alarm_audio repeat" if repeat else "play widget_alarm_audio"
        res = mci(play_cmd, None, 0, 0)
        return res == 0
    except Exception:
        return False


def stop_mp3_sound():
    """توقف کامل پخش صدای MP3 آلارم"""
    global _linux_audio_proc
    if not IS_WIN:
        if _linux_audio_proc is not None:
            try:
                _linux_audio_proc.terminate()
            except Exception:
                pass
            _linux_audio_proc = None
        return
    try:
        mci = ctypes.windll.winmm.mciSendStringW
        mci("stop widget_alarm_audio", None, 0, 0)
        mci("close widget_alarm_audio", None, 0, 0)
    except Exception:
        pass


def enable_dpi_awareness():
    """فعال‌سازی پشتیبانی از نمایشگرهای High-DPI برای وضوح کامل فونت‌ها"""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def register_bundled_fonts() -> list[str]:
    """
    بارگذاری فونت‌های فارسی باندل‌شده در assets/fonts:
    - در ویندوز: با AddFontResourceExW در حافظه GDI
    - در لینوکس: کپی خودکار در ~/.local/share/fonts و به‌روزرسانی fc-cache
    """
    loaded = []
    fonts_dir = get_resource_path(os.path.join("assets", "fonts"))
    if not os.path.isdir(fonts_dir):
        return loaded

    if not IS_WIN:
        user_fonts = os.path.expanduser("~/.local/share/fonts/PersianClockWidget")
        os.makedirs(user_fonts, exist_ok=True)
        copied_new = False
        for fname in os.listdir(fonts_dir):
            if fname.lower().endswith((".ttf", ".otf")):
                src_p = os.path.join(fonts_dir, fname)
                dst_p = os.path.join(user_fonts, fname)
                try:
                    if not os.path.exists(dst_p):
                        shutil.copy2(src_p, dst_p)
                        copied_new = True
                    loaded.append(dst_p)
                except Exception:
                    pass
        if copied_new and shutil.which("fc-cache"):
            try:
                subprocess.Popen(["fc-cache", "-f", user_fonts], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return loaded

    FR_PRIVATE = 0x10
    for fname in os.listdir(fonts_dir):
        if fname.lower().endswith((".ttf", ".otf")):
            fpath = os.path.join(fonts_dir, fname)
            try:
                res = ctypes.windll.gdi32.AddFontResourceExW(
                    ctypes.c_wchar_p(fpath),
                    FR_PRIVATE,
                    0,
                )
                if res > 0:
                    loaded.append(fpath)
            except Exception:
                pass
    return loaded


def get_hwnd(tk_win) -> int:
    """دریافت هندل واقعی پنجره ویندوز (HWND) از پنجره Tkinter"""
    tk_win.update_idletasks()
    if not IS_WIN:
        return tk_win.winfo_id()
    hwnd = ctypes.windll.user32.GetParent(tk_win.winfo_id())
    if not hwnd:
        hwnd = tk_win.winfo_id()
    return hwnd


def hide_from_taskbar(tk_win):
    """مخفی کردن کامل پنجره از Taskbar و Alt+Tab"""
    if not IS_WIN:
        try:
            tk_win.attributes("-type", "utility")
        except Exception:
            pass
        return
    try:
        hwnd = get_hwnd(tk_win)
        user32 = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if new_style != ex_style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
    except Exception:
        pass


def apply_z_order_and_clickthrough(tk_win, z_mode: str, click_through: bool = False):
    """اعمال حالت Z-Index و قفل عبوردهی کلیک (Click-Through)"""
    if not IS_WIN:
        try:
            is_topmost = (z_mode != "desktop")
            tk_win.attributes("-topmost", is_topmost)
            if not is_topmost:
                tk_win.lower()
        except Exception:
            pass
        return
    try:
        hwnd = get_hwnd(tk_win)
        user32 = ctypes.windll.user32

        is_topmost = (z_mode != "desktop")

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        target_style = (ex_style | WS_EX_TOOLWINDOW | WS_EX_LAYERED) & ~WS_EX_APPWINDOW
        if click_through:
            target_style |= WS_EX_TRANSPARENT
        else:
            target_style &= ~WS_EX_TRANSPARENT

        if target_style != ex_style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, target_style)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )

        if is_topmost:
            tk_win.attributes("-topmost", True)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        else:
            tk_win.attributes("-topmost", False)
            user32.SetWindowPos(
                hwnd,
                HWND_BOTTOM,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
    except Exception:
        pass


def apply_rounded_corners(tk_win, width: int, height: int, radius: int = 16, enabled: bool = True):
    """اعمال گوشه‌های گرد به پنجره ویجت در ویندوز 11 و 10"""
    if not IS_WIN:
        return
    try:
        hwnd = get_hwnd(tk_win)
        pref = ctypes.c_int(DWMWCP_ROUND if enabled else DWMWCP_DONOTROUND)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(pref),
            ctypes.sizeof(pref),
        )
        if res != 0:
            if enabled:
                rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
                ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
            else:
                ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# مدیریت اجرای خودکار با شروع ویندوز (Startup)
# ---------------------------------------------------------------------------
def get_startup_command(script_path: str) -> str:
    if getattr(sys, "frozen", False):
        return f'"{os.path.abspath(sys.executable)}"'
    python_exe = sys.executable
    pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
    if os.path.exists(pythonw_exe):
        python_exe = pythonw_exe
    return f'"{python_exe}" "{os.path.abspath(script_path)}"'


def _linux_autostart_path() -> str:
    return os.path.expanduser("~/.config/autostart/persian-clock-widget.desktop")


def is_startup_enabled() -> bool:
    if not IS_WIN:
        return os.path.exists(_linux_autostart_path())
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        )
        val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False


def set_startup_enabled(enable: bool, script_path: str) -> bool:
    if not IS_WIN:
        desktop_path = _linux_autostart_path()
        try:
            if enable:
                os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
                exec_cmd = get_startup_command(script_path)
                icon_path = get_resource_path(os.path.join("assets", "icons", "app_icon.png"))
                with open(desktop_path, "w", encoding="utf-8") as f:
                    f.write(
                        "[Desktop Entry]\n"
                        "Type=Application\n"
                        "Name=Persian Clock & Calendar\n"
                        f"Exec={exec_cmd}\n"
                        f"Icon={icon_path}\n"
                        "Terminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            else:
                if os.path.exists(desktop_path):
                    os.remove(desktop_path)
            return True
        except Exception:
            return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        if enable:
            cmd = get_startup_command(script_path)
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# مدیریت آیکون کنار ساعت ویندوز (Hidden Icons / System Tray)
# ---------------------------------------------------------------------------
class SystemTrayIcon:
    WM_TRAYICON = win32con.WM_USER + 20 if HAS_WIN32 else 0x0414

    def __init__(self, tooltip: str, on_left_click, on_right_click):
        self.tooltip = tooltip
        self.on_left_click = on_left_click
        self.on_right_click = on_right_click
        self.hwnd = None
        self._thread = None
        self._running = False

    def start(self):
        if not HAS_WIN32 or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def update_tooltip(self, new_tooltip: str):
        self.tooltip = new_tooltip[:120]
        if HAS_WIN32 and self.hwnd:
            try:
                nid = (
                    self.hwnd,
                    0,
                    win32gui.NIF_TIP,
                    self.WM_TRAYICON,
                    0,
                    self.tooltip,
                )
                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
            except Exception:
                pass

    def stop(self):
        self._running = False
        if HAS_WIN32 and self.hwnd:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
            self.hwnd = None

    def _run(self):
        try:
            message_map = {
                win32con.WM_DESTROY: self._on_destroy,
                self.WM_TRAYICON: self._on_notify,
            }
            wc = win32gui.WNDCLASS()
            hinst = wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = "PersianClockWidgetTrayClass"
            wc.lpfnWndProc = message_map
            try:
                class_atom = win32gui.RegisterClass(wc)
            except Exception:
                class_atom = wc.lpszClassName

            self.hwnd = win32gui.CreateWindow(
                class_atom,
                "PersianClockWidgetTray",
                0,
                0, 0, 0, 0,
                0, 0, hinst, None,
            )

            hicon = None
            ico_path = get_resource_path(os.path.join("assets", "icons", "app_icon.ico"))
            if os.path.exists(ico_path):
                try:
                    hicon = win32gui.LoadImage(
                        hinst,
                        ico_path,
                        win32con.IMAGE_ICON,
                        0, 0,
                        win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
                    )
                except Exception:
                    hicon = None
            if not hicon:
                hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

            flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            nid = (self.hwnd, 0, flags, self.WM_TRAYICON, hicon, self.tooltip[:120])
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

            win32gui.PumpMessages()
        except Exception:
            pass

    def _on_notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP or lparam == win32con.WM_LBUTTONDBLCLK:
            if self.on_left_click:
                self.on_left_click()
        elif lparam == win32con.WM_RBUTTONUP:
            if self.on_right_click:
                self.on_right_click()
        return True

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
        except Exception:
            pass
        win32gui.PostQuitMessage(0)
        return True
