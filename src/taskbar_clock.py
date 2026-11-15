# -*- coding: utf-8 -*-
"""
نمایش ساعت و تاریخ شمسی در تسک‌بار ویندوز:

۱. WindowsClockReplacer: جایگزینی کامل ساعت و تاریخ پیش‌فرض انگلیسی ویندوز
   - یک باکس سالید و مات که دقیقاً روی ساعت و تاریخ ویندوز در گوشه تسک‌بار می‌نشیند
   - ساعت انگلیسی ویندوز را ۱۰۰٪ می‌پوشاند و مخفی می‌کند
   - ساعت تهران و تاریخ شمسی را با فونت وزیر و خط دور مشکی نمایش می‌دهد
   - کلیک چپ: باز/بسته کردن تقویم ماهانه
   - کلیک راست: منوی تنظیمات
   - قابلیت جابه‌جایی دستی با کشیدن ماوس (Drag)

۲. TaskbarClockOverlay: ساعت و تاریخ شفاف شناور روی تسک‌بار (کنار ساعت ویندوز)

۳. TaskbarButtonProxy: آیکون/دکمه برنامه در تسک‌بار ویندوز

طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

import ctypes
from ctypes import wintypes
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont

try:
    import winreg
except ImportError:
    winreg = None

IS_WIN = sys.platform == "win32"

try:
    from src.alarm_manager import draw_outlined_canvas_text
    from src.win_utils import (
        apply_z_order_and_clickthrough,
        get_all_monitors,
        get_resource_path,
        hide_from_taskbar,
    )
except ImportError:
    from alarm_manager import draw_outlined_canvas_text
    from win_utils import (
        apply_z_order_and_clickthrough,
        get_all_monitors,
        get_resource_path,
        hide_from_taskbar,
    )

TB_TRANSPARENT_KEY = "#010204"


def get_taskbar_geometry():
    """
    دریافت مختصات تسک‌بار اصلی ویندوز با ترکیب SystemParametersInfo و Win32 API
    خروجی: (left, top, right, bottom, tray_left یا None)
    """
    if not IS_WIN:
        return 0, 1032, 1920, 1080, None
    try:
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        r = wintypes.RECT()
        # SPI_GETWORKAREA = 0x0030
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)

        if r.bottom < sh:
            tb_l, tb_t, tb_r, tb_b = 0, r.bottom, sw, sh
        elif r.top > 0:
            tb_l, tb_t, tb_r, tb_b = 0, 0, sw, r.top
        elif r.right < sw:
            tb_l, tb_t, tb_r, tb_b = r.right, 0, sw, sh
        elif r.left > 0:
            tb_l, tb_t, tb_r, tb_b = 0, 0, r.left, sh
        else:
            tb_l, tb_t, tb_r, tb_b = 0, sh - 48, sw, sh

        tray_left = None
        hwnd = user32.FindWindowW("Shell_TrayWnd", None)
        if hwnd:
            tray_hwnd = user32.FindWindowExW(hwnd, 0, "TrayNotifyWnd", None)
            if tray_hwnd:
                t_rect = wintypes.RECT()
                user32.GetWindowRect(tray_hwnd, ctypes.byref(t_rect))
                if tb_l <= t_rect.left < tb_r and (t_rect.right - t_rect.left) > 20:
                    tray_left = t_rect.left

        return tb_l, tb_t, tb_r, tb_b, tray_left
    except Exception:
        sw = 1920
        sh = 1080
        return 0, sh - 48, sw, sh, None


def get_all_taskbar_geometries() -> list[tuple[int, int, int, int, int | None]]:
    """
    دریافت مختصات تمام تسک‌بارهای ویندوز در سیستم‌های تک‌مانیتوره و چندمانیتوره
    (Shell_TrayWnd + تمام Shell_SecondaryTrayWnd ها)
    خروجی: لیستی از (left, top, right, bottom, tray_left)
    """
    if not IS_WIN:
        return [get_taskbar_geometry()]

    geos: list[tuple[int, int, int, int, int | None]] = []
    try:
        user32 = ctypes.windll.user32

        # ۱. تسک‌بار اصلی (Shell_TrayWnd)
        primary_geo = get_taskbar_geometry()
        if primary_geo:
            geos.append(primary_geo)

        # ۲. تمام تسک‌بارهای مانیتورهای دوم و بعدی (Shell_SecondaryTrayWnd)
        prev = 0
        for _ in range(16):
            sec_hwnd = user32.FindWindowExW(0, prev, "Shell_SecondaryTrayWnd", None)
            if not sec_hwnd:
                break
            prev = sec_hwnd
            if user32.IsWindowVisible(sec_hwnd):
                r = wintypes.RECT()
                if user32.GetWindowRect(sec_hwnd, ctypes.byref(r)):
                    if (r.right - r.left) > 20 and (r.bottom - r.top) > 10:
                        geos.append((int(r.left), int(r.top), int(r.right), int(r.bottom), None))
    except Exception:
        pass

    if not geos:
        geos.append(get_taskbar_geometry())
    return geos


def is_taskbar_light_theme() -> bool:
    """تشخیص تم روشن یا تاریک تسک‌بار ویندوز از رجیستری"""
    if not IS_WIN or winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            return int(val) == 1
    except Exception:
        return False


def detect_taskbar_colors(tb_l: int, tb_t: int, tb_r: int, tb_b: int) -> tuple[str, str, bool]:
    """
    تشخیص دقیق رنگ پس‌زمینه تسک‌بار با نمونه‌برداری پیکسل و بررسی تم ویندوز
    خروجی: (base_bg_hex, hover_bg_hex, is_light)
    """
    is_light = is_taskbar_light_theme()
    default_bg = "#EEEEEE" if is_light else "#1C1C1C"
    default_hover = "#DFDFDF" if is_light else "#2B2B2B"
    if not IS_WIN:
        return default_bg, default_hover, is_light
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if hdc:
            sample_x = max(tb_l + 12, tb_r - 240)
            sample_y = tb_t + max(4, (tb_b - tb_t) // 4)
            color_ref = gdi32.GetPixel(hdc, int(sample_x), int(sample_y))
            user32.ReleaseDC(0, hdc)
            if color_ref != -1 and color_ref != 0xFFFFFFFF:
                r = color_ref & 0xFF
                g = (color_ref >> 8) & 0xFF
                b = (color_ref >> 16) & 0xFF
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                # اطمینان از همخوانی منطقی با تم روشن/تیره (تا رنگ تصادفی آیکون یا خطا نگیرد)
                if (not is_light and lum < 110) or (is_light and lum > 150):
                    bg_hex = f"#{r:02X}{g:02X}{b:02X}"
                    if is_light:
                        hr, hg, hb = max(0, r - 18), max(0, g - 18), max(0, b - 18)
                    else:
                        hr, hg, hb = min(255, r + 18), min(255, g + 18), min(255, b + 18)
                    hover_hex = f"#{hr:02X}{hg:02X}{hb:02X}"
                    return bg_hex, hover_hex, (lum > 145)
    except Exception:
        pass
    return default_bg, default_hover, is_light


def find_win10_tray_clock_hwnd() -> int | None:
    """یافتن پنجره ساعت کلاسیک ویندوز ۱۰ (TrayClockWClass) در صورت وجود"""
    if not IS_WIN:
        return None
    try:
        user32 = ctypes.windll.user32
        shell = user32.FindWindowW("Shell_TrayWnd", None)
        if not shell:
            return None
        tray = user32.FindWindowExW(shell, 0, "TrayNotifyWnd", None)
        if not tray:
            return None
        clk = user32.FindWindowExW(tray, 0, "TrayClockWClass", None)
        return int(clk) if clk else None
    except Exception:
        return None


def get_windows11_tray_clock_hidden() -> bool:
    """بررسی وضعیت مخفی بودن ساعت و تاریخ انگلیسی در تنظیمات تسک‌بار ویندوز ۱۱"""
    if not IS_WIN or winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "HideSystrayDateTimeValueName")
            return int(val) == 1
    except Exception:
        return False


def set_windows11_tray_clock_hidden(hide: bool) -> bool:
    """
    تنظیم کلید رسمی ویندوز ۱۱ برای نمایش یا حذف ساعت و تاریخ انگلیسی در تسک‌بار:
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced\\HideSystrayDateTimeValueName
    """
    if not IS_WIN or winreg is None:
        return False
    try:
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        ) as key:
            winreg.SetValueEx(key, "HideSystrayDateTimeValueName", 0, winreg.REG_DWORD, 1 if hide else 0)
        # اطلاع‌رسانی به Explorer برای اعمال تنظیمات
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "TraySettings", 0x0002, 500, None)
        return True
    except Exception:
        return False


class _SingleTaskbarReplacer:
    """
    جایگزینی کامل ساعت و تاریخ ویندوز روی یک تسک‌بار مشخص (مانیتور اصلی یا ثانویه)
    """

    def __init__(self, app, taskbar_index: int = 0):
        self.app = app
        self.root = app.root
        self.taskbar_index = taskbar_index
        self._current_geo: tuple[int, int, int, int, int | None] | None = None
        self._press_x = 0
        self._press_win_x = 0
        self._dragged = False
        self._last_w = 0
        self._last_h = 0
        self._last_rel_x = 0
        self._last_rel_y = 0
        self._is_hovered = False
        self._last_info: dict | None = None
        self._tip_win: tk.Toplevel | None = None
        self._tip_timer: str | None = None
        self._embedded_parent_hwnd: int | None = None
        self._hidden_win10_clock_hwnd: int | None = None
        self._last_color_probe_ts = 0.0
        self._is_light_tb = is_taskbar_light_theme()

        self.win = tk.Toplevel(self.root)
        self.win.title("WindowsClockReplacer")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        self.base_bg = "#EEEEEE" if self._is_light_tb else "#1C1C1C"
        self.hover_bg = "#DFDFDF" if self._is_light_tb else "#2B2B2B"
        self.win.configure(bg=self.base_bg)

        self.canvas = tk.Canvas(
            self.win,
            bg=self.base_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        # بایندینگ فقط روی canvas (نه self.win) تا رویداد کلیک دوبار اجرا نشود
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        self.win.after(50, self._attach_to_taskbar)

    def _on_enter(self, event=None):
        self._is_hovered = True
        self.canvas.configure(bg=self.hover_bg)
        self.win.configure(bg=self.hover_bg)
        if self._tip_timer:
            try:
                self.win.after_cancel(self._tip_timer)
            except Exception:
                pass
        self._tip_timer = self.win.after(120, self._show_tip)

    def _on_leave(self, event=None):
        self._is_hovered = False
        if self._tip_timer:
            try:
                self.win.after_cancel(self._tip_timer)
            except Exception:
                pass
            self._tip_timer = None
        self.canvas.configure(bg=self.base_bg)
        self.win.configure(bg=self.base_bg)
        self._hide_tip()

    def _show_tip(self):
        if not self._is_hovered or self._tip_win is not None or not self._last_info:
            return
        info = self._last_info
        day_n = info.get("day_name", "")
        dt_txt = info.get("date_text", "")
        occ = info.get("occasion_text")
        tip_text = f"{day_n} {dt_txt}"
        if occ:
            tip_text += f"\n{occ}"
        try:
            win = tk.Toplevel(self.win)
            self._tip_win = win
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            lbl = tk.Label(
                win,
                text=tip_text,
                font=(self.app.config.get("font_family", "Vazir"), 8, "bold"),
                bg="#0F172A",
                fg="#F8FAFC",
                bd=1,
                relief="solid",
                padx=8,
                pady=4,
                justify="center",
            )
            lbl.pack()
            win.update_idletasks()
            tw = win.winfo_reqwidth()
            th = win.winfo_reqheight()
            wx = self.win.winfo_rootx()
            wy = self.win.winfo_rooty()
            tx = max(8, wx + (self._last_w - tw) // 2)
            ty = max(8, wy - th - 6)
            win.geometry(f"+{int(tx)}+{int(ty)}")
            apply_z_order_and_clickthrough(win, "topmost", click_through=True)
        except Exception:
            pass

    def _hide_tip(self):
        if self._tip_win is not None:
            try:
                self._tip_win.destroy()
            except Exception:
                pass
            self._tip_win = None

    def _get_hwnd(self) -> int:
        self.win.update_idletasks()
        wid = self.win.winfo_id()
        try:
            root_hwnd = ctypes.windll.user32.GetAncestor(wid, 2)
            return int(root_hwnd) if root_hwnd else int(wid)
        except Exception:
            return int(wid)

    def _is_foreground_fullscreen(self) -> bool:
        if not IS_WIN:
            return False
        try:
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            if not fg or not user32.IsWindowVisible(fg):
                return False
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(fg, cls, 64)
            if cls.value in (
                "Shell_TrayWnd",
                "Shell_SecondaryTrayWnd",
                "Progman",
                "WorkerW",
                "TkTopLevel",
                "Windows.UI.Core.CoreWindow",
                "XamlExplorerHostIslandWindow",
                "TopLevelWindowForOverflowXamlIsland",
                "NotifyIconOverflowWindow",
                "SearchPane",
                "Shell_InputSwitchTopLevelWindow",
                "Xaml_WindowedPopupClass",
            ):
                return False
            # استثنا کردن تمام فرآیندهای شِل ویندوز (منوی استارت، جست‌وجو، تسک‌بار، ویجت‌ها و...)
            try:
                kernel32 = ctypes.windll.kernel32
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
                if pid.value:
                    h_proc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
                    if h_proc:
                        try:
                            buf = ctypes.create_unicode_buffer(260)
                            sz = wintypes.DWORD(260)
                            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(sz)):
                                exe_name = buf.value.rsplit("\\", 1)[-1].lower()
                                if exe_name in (
                                    "explorer.exe",
                                    "startmenuexperiencehost.exe",
                                    "searchhost.exe",
                                    "searchapp.exe",
                                    "shellexperiencehost.exe",
                                    "textinputhost.exe",
                                    "widgets.exe",
                                    "widgetservice.exe",
                                    "lockapp.exe",
                                ):
                                    return False
                        finally:
                            kernel32.CloseHandle(h_proc)
            except Exception:
                pass
            r = wintypes.RECT()
            user32.GetWindowRect(fg, ctypes.byref(r))
            geo = self._current_geo or get_taskbar_geometry()
            tb_l, tb_t, tb_r, tb_b, _ = geo
            cx = (tb_l + tb_r) // 2
            cy = (tb_t + tb_b) // 2
            mon_rect = None
            for m in get_all_monitors(self.win):
                ml, mt, mr, mb = m["rect"]
                if ml <= cx < mr and mt <= cy < mb:
                    mon_rect = (ml, mt, mr, mb)
                    break
            if mon_rect is None:
                return False
            ml, mt, mr, mb = mon_rect
            # بررسی تمام‌صفحه بودن پنجره فعال روی همین مانیتور
            return r.left <= ml and r.right >= mr and r.top <= mt and r.bottom >= mb
        except Exception:
            return False

    def _attach_to_taskbar(self):
        """تنظیم سبک غیرفعال‌ساز (بدون قفل شدن صف ورودی) و مخفی‌سازی ساعت ویندوز ۱۰ در صورت وجود"""
        if not IS_WIN or not self.win or not self.win.winfo_exists():
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = self._get_hwnd()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_ex = (ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            if new_ex != ex_style:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex)

            # در ویندوز ۱۰، ساعت کلاسیک TrayClockWClass را مستقیماً مخفی کن
            clk_hwnd = find_win10_tray_clock_hwnd()
            if clk_hwnd and clk_hwnd != self._hidden_win10_clock_hwnd:
                user32.ShowWindow(clk_hwnd, 0)  # SW_HIDE
                self._hidden_win10_clock_hwnd = clk_hwnd
        except Exception:
            hide_from_taskbar(self.win)

    def _position_in_taskbar(self, x: int, y: int, w: int, h: int, tb_l: int, tb_t: int):
        """قرار دادن پنجره دقیقاً در مختصات تسک‌بار"""
        if self._is_foreground_fullscreen():
            if self.win.winfo_viewable():
                self.win.withdraw()
            return
        if not self.win.winfo_viewable():
            self.win.deiconify()
        self.win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
        self.keep_on_top()

    def refresh(self, info: dict, geo: tuple[int, int, int, int, int | None] | None = None):
        if not self.win or not self.win.winfo_exists():
            return
        self._last_info = info
        cfg = self.app.config
        use_fa = cfg.get("persian_digits", False)
        font_fa = cfg.get("font_family", "Vazir")
        font_clock = cfg.get("clock_font_family", "Vazir")

        if geo is None:
            geos = get_all_taskbar_geometries()
            geo = geos[self.taskbar_index] if self.taskbar_index < len(geos) else geos[0]
        self._current_geo = geo
        tb_l, tb_t, tb_r, tb_b, _ = geo

        if not self._embedded_parent_hwnd:
            self._attach_to_taskbar()

        # تشخیص خودکار رنگ تسک‌بار هر ۱۰ ثانیه (در حالت auto)
        bg_cfg = cfg.get("replace_clock_bg", "auto")
        if bg_cfg == "auto" or not bg_cfg:
            now_ts = time.monotonic()
            if now_ts - self._last_color_probe_ts > 10.0:
                self._last_color_probe_ts = now_ts
                self.base_bg, self.hover_bg, self._is_light_tb = detect_taskbar_colors(tb_l, tb_t, tb_r, tb_b)
        else:
            self.base_bg = bg_cfg
            self._is_light_tb = False
            self.hover_bg = "#2B2B2B"

        tb_w = tb_r - tb_l
        tb_h = tb_b - tb_t
        horizontal = tb_w >= tb_h

        # متن ساعت
        base_hm = str(info.get("time_str", ""))[:5]
        if cfg.get("show_seconds", False) or cfg.get("taskbar_clock_seconds", False):
            time_txt = f"{base_hm}:{int(info.get('second', 0)):02d}"
        else:
            time_txt = base_hm
        time_txt = self.app.format_digits_public(time_txt, use_fa)

        # متن تاریخ شمسی (کوتاه و استاندارد برای قرارگیری در تسک‌بار)
        jy = info.get("jy")
        jm = info.get("jm")
        jd = info.get("jd")
        date_txt = f"{jy:04d}/{jm:02d}/{jd:02d}"
        date_txt = self.app.format_digits_public(date_txt, use_fa)

        # عرض و ارتفاع باکس پوشش ساعت ویندوز
        win_w = int(cfg.get("replace_clock_width", 118))
        win_h = tb_h if horizontal else 56

        # موقعیت: دقیقاً روی ساعت پیش‌فرض ویندوز در گوشه راست تسک‌بار
        saved_off = cfg.get("replace_clock_offset", 8)
        if horizontal:
            x = tb_r - win_w - int(saved_off)
            y = tb_t
        else:
            x = tb_l
            y = tb_b - win_h - int(saved_off)

        self.canvas.delete("all")
        self.canvas.configure(width=win_w, height=win_h)
        bg = self.hover_bg if self._is_hovered else self.base_bg
        self.canvas.configure(bg=bg)
        self.win.configure(bg=bg)

        # حاشیه ملایم در حالت Hover
        if self._is_hovered:
            outline_c = "#CBD5E1" if self._is_light_tb else "#334155"
            self.canvas.create_rectangle(1, 1, win_w - 2, win_h - 2, outline=outline_c, width=1)

        is_hol = bool(info.get("is_holiday"))
        if self._is_light_tb and (bg_cfg == "auto" or not bg_cfg):
            clock_color = "#0F172A"
            date_color = "#DC2626" if is_hol else "#334155"
        else:
            clock_color = cfg.get("clock_color", "#F8FAFC")
            date_color = cfg.get("holiday_color", "#F87171") if is_hol else cfg.get("date_color", "#CBD5E1")

        # موقعیت عمودی هماهنگ با تسک‌بار ویندوز ۱۰ و ۱۱
        y_time = max(3, int(win_h * 0.10))
        y_date = max(y_time + 17, int(win_h * 0.52))

        if self._is_light_tb and (bg_cfg == "auto" or not bg_cfg):
            self.canvas.create_text(
                win_w // 2,
                y_time,
                text=time_txt,
                font=(font_clock, 10, "bold"),
                fill=clock_color,
                anchor="n",
            )
            self.canvas.create_text(
                win_w // 2,
                y_date,
                text=date_txt,
                font=(font_fa, 8, "bold"),
                fill=date_color,
                anchor="n",
            )
        else:
            # خط ۱: ساعت به وقت تهران
            draw_outlined_canvas_text(
                self.canvas,
                win_w // 2,
                y_time,
                text=time_txt,
                font_spec=(font_clock, 10, "bold"),
                fill=clock_color,
                outline="#000000",
                anchor="n",
            )

            # خط ۲: تاریخ شمسی
            draw_outlined_canvas_text(
                self.canvas,
                win_w // 2,
                y_date,
                text=date_txt,
                font_spec=(font_fa, 8, "bold"),
                fill=date_color,
                outline="#000000",
                anchor="n",
            )

        self._last_w, self._last_h = win_w, win_h
        if not self._dragged:
            self._position_in_taskbar(x, y, win_w, win_h, tb_l, tb_t)
        else:
            self.keep_on_top()

    def keep_on_top(self):
        if not self.win or not self.win.winfo_exists():
            return
        if self._is_foreground_fullscreen():
            if self.win.winfo_viewable():
                self.win.withdraw()
            return
        if not self.win.winfo_viewable():
            self.win.deiconify()
        apply_z_order_and_clickthrough(self.win, "topmost", click_through=False)

    def _on_press(self, event):
        self._hide_tip()
        self._press_x = event.x_root
        self._press_win_x = self.win.winfo_rootx()
        self._dragged = False
        return "break"

    def _on_motion(self, event):
        dx = event.x_root - self._press_x
        if abs(dx) > 4:
            self._dragged = True
        if self._dragged:
            geo = self._current_geo or get_taskbar_geometry()
            new_x = self._press_win_x + dx
            tb_l, tb_t = 0, self.win.winfo_rooty()
            if geo:
                tb_l, tb_t, tb_r, _, _ = geo
                new_x = max(tb_l, min(new_x, tb_r - self._last_w))
            self._position_in_taskbar(int(new_x), int(tb_t), self._last_w, self._last_h, tb_l, tb_t)
        return "break"

    def _on_release(self, event):
        if self._dragged:
            geo = self._current_geo or get_taskbar_geometry()
            tb_r = geo[2] if geo else self.root.winfo_screenwidth()
            cur_x = self.win.winfo_rootx()
            offset = tb_r - (cur_x + self._last_w)
            self.app.config["replace_clock_offset"] = max(-10, min(800, int(offset)))
            self.app._save_config()
            self._dragged = False
            return "break"
        self.app.on_taskbar_clicked()
        return "break"

    def _on_right_click(self, event):
        self._hide_tip()
        self.app.show_menu_at_pointer()
        return "break"

    def destroy(self):
        if self._tip_timer:
            try:
                self.win.after_cancel(self._tip_timer)
            except Exception:
                pass
            self._tip_timer = None
        self._hide_tip()
        try:
            user32 = ctypes.windll.user32
            if self._hidden_win10_clock_hwnd:
                user32.ShowWindow(self._hidden_win10_clock_hwnd, 5)  # SW_SHOW
                self._hidden_win10_clock_hwnd = None
            if self._embedded_parent_hwnd and self.win and self.win.winfo_exists():
                user32.SetParent(self._get_hwnd(), 0)
                self._embedded_parent_hwnd = None
        except Exception:
            pass
        try:
            if self.win and self.win.winfo_exists():
                self.win.destroy()
        except Exception:
            pass
        self.win = None


class WindowsClockReplacer:
    """
    مدیریت جایگزینی ساعت و تاریخ ویندوز روی همه مانیتورها (تک‌مانیتوره و چندمانیتوره)
    """

    def __init__(self, app):
        self.app = app
        self._replacers: list[_SingleTaskbarReplacer] = []
        self._sync_monitors()

    @property
    def _last_color_probe_ts(self) -> float:
        return self._replacers[0]._last_color_probe_ts if self._replacers else 0.0

    @_last_color_probe_ts.setter
    def _last_color_probe_ts(self, val: float):
        for r in self._replacers:
            r._last_color_probe_ts = val

    def _sync_monitors(self) -> list[tuple[int, int, int, int, int | None]]:
        geos = get_all_taskbar_geometries()
        while len(self._replacers) < len(geos):
            idx = len(self._replacers)
            self._replacers.append(_SingleTaskbarReplacer(self.app, taskbar_index=idx))
        while len(self._replacers) > len(geos):
            extra = self._replacers.pop()
            extra.destroy()
        return geos

    def refresh(self, info: dict):
        geos = self._sync_monitors()
        for replacer, geo in zip(self._replacers, geos):
            replacer.refresh(info, geo=geo)

    def keep_on_top(self):
        for replacer in self._replacers:
            replacer.keep_on_top()

    def destroy(self):
        for replacer in self._replacers:
            replacer.destroy()
        self._replacers.clear()


class TaskbarClockOverlay:
    """ساعت و تاریخ شمسی شناور و شفاف روی نوار تسک‌بار (کنار ساعت ویندوز)"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self._press_x = 0
        self._press_win_x = 0
        self._dragged = False
        self._last_w = 0
        self._last_h = 0

        self.win = tk.Toplevel(self.root)
        self.win.title("PersianTaskbarClock")
        self.win.overrideredirect(True)
        self.win.configure(bg=TB_TRANSPARENT_KEY)
        self.win.attributes("-transparentcolor", TB_TRANSPARENT_KEY)

        self.canvas = tk.Canvas(
            self.win,
            bg=TB_TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        # بایندینگ فقط روی canvas تا رویداد کلیک دوبار اجرا نشود
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)

        self.win.after(50, lambda: hide_from_taskbar(self.win))

    def _measure(self, text: str, font_spec: tuple) -> tuple[int, int]:
        f = tkfont.Font(family=font_spec[0], size=font_spec[1], weight="bold")
        return f.measure(text), f.metrics("linespace")

    def refresh(self, info: dict):
        if not self.win or not self.win.winfo_exists():
            return
        cfg = self.app.config
        use_fa = cfg.get("persian_digits", False)
        font_fa = cfg.get("font_family", "Vazir")
        font_clock = cfg.get("clock_font_family", "Vazir")

        geo = get_taskbar_geometry()
        if geo:
            tb_l, tb_t, tb_r, tb_b, tray_left = geo
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            tb_l, tb_t, tb_r, tb_b, tray_left = 0, sh - 48, sw, sh, None

        tb_w = tb_r - tb_l
        tb_h = tb_b - tb_t
        horizontal = tb_w >= tb_h

        base_hm = str(info.get("time_str", ""))[:5]
        if cfg.get("show_seconds", False) or cfg.get("taskbar_clock_seconds", False):
            time_txt = f"{base_hm}:{int(info.get('second', 0)):02d}"
        else:
            time_txt = base_hm
        date_txt = f"{info.get('weekday_name', '')} {info.get('date_numeric', '')}"
        if info.get("has_occasion") and info.get("is_holiday"):
            date_txt += " • تعطیل"

        time_txt = self.app.format_digits_public(time_txt, use_fa)
        date_txt = self.app.format_digits_public(date_txt, use_fa)

        bar_h = tb_h if horizontal else 56
        t_size = 10 if bar_h >= 44 else 9
        d_size = 8 if bar_h >= 44 else 7
        t_spec = (font_clock, t_size, "bold")
        d_spec = (font_fa, d_size, "bold")
        tw, th = self._measure(time_txt, t_spec)
        dw, dh = self._measure(date_txt, d_spec)

        win_w = max(tw, dw) + 16
        win_h = bar_h if horizontal else (th + dh + 10)
        if not horizontal:
            win_w = tb_w

        if horizontal:
            saved_off = cfg.get("taskbar_clock_offset")
            if saved_off is None:
                anchor_right = (tray_left if tray_left else tb_r - 240) - 6
                x = anchor_right - win_w
            else:
                x = tb_r - int(saved_off) - win_w
            x = max(tb_l, min(x, tb_r - win_w))
            y = tb_t
        else:
            x = tb_l
            y = tb_b - win_h - 110

        self.canvas.delete("all")
        self.canvas.configure(width=win_w, height=win_h)
        total_text_h = th + dh
        top = max(0, (win_h - total_text_h) // 2)
        is_hol = bool(info.get("is_holiday"))
        draw_outlined_canvas_text(
            self.canvas,
            win_w // 2,
            top,
            text=time_txt,
            font_spec=t_spec,
            fill=cfg.get("clock_color", "#F8FAFC"),
            outline="#000000",
            anchor="n",
        )
        draw_outlined_canvas_text(
            self.canvas,
            win_w // 2,
            top + th,
            text=date_txt,
            font_spec=d_spec,
            fill=cfg.get("holiday_color", "#F87171") if is_hol else cfg.get("date_color", "#CBD5E1"),
            outline="#000000",
            anchor="n",
        )

        self._last_w, self._last_h = win_w, win_h

        if not self._dragged:
            self.win.geometry(f"{int(win_w)}x{int(win_h)}+{int(x)}+{int(y)}")
        self.keep_on_top()

    def keep_on_top(self):
        if self.win and self.win.winfo_exists():
            apply_z_order_and_clickthrough(self.win, "topmost", click_through=False)

    def _on_press(self, event):
        self._press_x = event.x_root
        self._press_win_x = self.win.winfo_x()
        self._dragged = False

    def _on_motion(self, event):
        dx = event.x_root - self._press_x
        if abs(dx) > 4:
            self._dragged = True
        if self._dragged:
            geo = get_taskbar_geometry()
            new_x = self._press_win_x + dx
            if geo:
                tb_l, _, tb_r, _, _ = geo
                new_x = max(tb_l, min(new_x, tb_r - self._last_w))
            self.win.geometry(f"+{int(new_x)}+{self.win.winfo_y()}")

    def _on_release(self, event):
        if self._dragged:
            geo = get_taskbar_geometry()
            tb_r = geo[2] if geo else self.root.winfo_screenwidth()
            offset = tb_r - (self.win.winfo_x() + self._last_w)
            self.app.config["taskbar_clock_offset"] = int(offset)
            self.app._save_config()
            self._dragged = False
            return
        self.app.on_taskbar_clicked()

    def _on_right_click(self, event):
        self.app.show_menu_at_pointer()

    def destroy(self):
        try:
            if self.win and self.win.winfo_exists():
                self.win.destroy()
        except Exception:
            pass
        self.win = None


class TaskbarButtonProxy:
    """دکمه/آیکون معمولی برنامه در تسک‌بار ویندوز"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self._busy = False

        self.win = tk.Toplevel(self.root)
        self.win.title("ساعت و تقویم شمسی")
        self.win.geometry("1x1+-32000+-32000")
        self.win.attributes("-alpha", 0.0)
        ico_path = get_resource_path(os.path.join("assets", "icons", "app_icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.win.iconbitmap(ico_path)
            except Exception:
                pass
        self.win.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.win.update_idletasks()
        self.win.iconify()
        self.win.bind("<Map>", self._on_map)

    def _on_map(self, event=None):
        if self._busy or event is None or event.widget is not self.win:
            return
        if self.win.state() != "normal":
            return
        self._busy = True

        def _act():
            try:
                self.win.iconify()
            except Exception:
                pass
            self.app.on_taskbar_clicked()
            self.win.after(250, self._release)

        self.win.after(10, _act)

    def _release(self):
        self._busy = False

    def _on_close_request(self):
        self.app.config["taskbar_button"] = False
        self.app._save_config()
        self.app.sync_taskbar_features()

    def update_title(self, text: str):
        try:
            if self.win and self.win.winfo_exists():
                self.win.title(text)
        except Exception:
            pass

    def destroy(self):
        try:
            if self.win and self.win.winfo_exists():
                self.win.destroy()
        except Exception:
            pass
        self.win = None
