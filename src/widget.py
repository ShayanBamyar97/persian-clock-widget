# -*- coding: utf-8 -*-
"""
ویجت حرفه‌ای ساعت تهران، تقویم شمسی، مناسبت‌ها، ابزار کپی زمان برنامه‌نویسی (۱۰ فرمت API + تولیدکننده GUID) و سیستم آلارم/رویداد
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

from datetime import datetime, timezone
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, font as tkfont, ttk
import uuid

try:
    from src.alarm_manager import (
        AlarmManagerWindow,
        AlarmStore,
        AnimatedBellPopup,
        draw_outlined_canvas_text,
    )
    from src.calendar_data import (
        PERSIAN_MONTHS,
        PERSIAN_WEEK_SHORT,
        TEHRAN_TZ,
        get_jalali_month_days,
        get_month_calendar,
        get_today_info,
        gregorian_to_jalali,
    )
    from src.win_utils import (
        SystemTrayIcon,
        apply_rounded_corners,
        apply_z_order_and_clickthrough,
        enable_dpi_awareness,
        get_data_dir,
        get_monitor_work_area_at,
        get_resource_path,
        hide_from_taskbar,
        is_startup_enabled,
        register_bundled_fonts,
        set_startup_enabled,
    )
    from src.taskbar_clock import (
        TaskbarButtonProxy,
        TaskbarClockOverlay,
        WindowsClockReplacer,
        get_windows11_tray_clock_hidden,
        set_windows11_tray_clock_hidden,
    )
    from src.ip_monitor import IpHistoryStore, check_ip_lock_mismatch, fetch_ip_geolocation
    from src.dev_ai_hub import DevAiHubWindow
    from src.local_api import DEFAULT_API_PORT, LocalWidgetApiServer
    from src.scheduler_actions import execute_scheduled_action
except ImportError:
    from alarm_manager import (
        AlarmManagerWindow,
        AlarmStore,
        AnimatedBellPopup,
        draw_outlined_canvas_text,
    )
    from calendar_data import (
        PERSIAN_MONTHS,
        PERSIAN_WEEK_SHORT,
        TEHRAN_TZ,
        get_jalali_month_days,
        get_month_calendar,
        get_today_info,
        gregorian_to_jalali,
    )
    from win_utils import (
        SystemTrayIcon,
        apply_rounded_corners,
        apply_z_order_and_clickthrough,
        enable_dpi_awareness,
        get_data_dir,
        get_monitor_work_area_at,
        get_resource_path,
        hide_from_taskbar,
        is_startup_enabled,
        register_bundled_fonts,
        set_startup_enabled,
    )
    from taskbar_clock import (
        TaskbarButtonProxy,
        TaskbarClockOverlay,
        WindowsClockReplacer,
        get_windows11_tray_clock_hidden,
        set_windows11_tray_clock_hidden,
    )
    from ip_monitor import IpHistoryStore, check_ip_lock_mismatch, fetch_ip_geolocation
    from dev_ai_hub import DevAiHubWindow
    from local_api import DEFAULT_API_PORT, LocalWidgetApiServer
    from scheduler_actions import execute_scheduled_action

DATA_DIR = get_data_dir()
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
CUSTOM_OCCASIONS_PATH = os.path.join(DATA_DIR, "custom_occasions.json")
ALARMS_PATH = os.path.join(DATA_DIR, "alarms.json")

TRANSPARENT_KEY = "#010203"

DEFAULT_CONFIG = {
    "x": None,
    "y": None,
    "locked": False,            # False = آزاد (🔓) | True = فیکس و Click-Through (🔒)
    "z_mode": "topmost",        # 'topmost' (همیشه روی برنامه‌ها) یا 'desktop' (چسبیده به دسکتاپ)
    "opacity": 0.90,
    "transparent_bg": False,
    "persian_digits": False,
    "calendar_expanded": False,
    "calendar_position": "beside",
    # تنظیمات رنگ‌ها
    "bg_color": "#141821",
    "border_color": "#2A3244",
    "clock_color": "#F8FAFC",
    "date_color": "#CBD5E1",
    "occasion_color": "#94A3B8",
    "holiday_color": "#F87171",
    "accent_color": "#38BDF8",
    # تنظیمات سایز ویجت و فونت‌ها (با پیش‌فرض فونت وزیر Vazir)
    "widget_scale": 100,
    "font_family": "Vazir",
    "clock_font_family": "Vazir",
    "clock_font_size": 26,
    "date_font_size": 11,
    "occasion_font_size": 9,
    # نمایش و جایگزینی در تسک‌بار ویندوز
    "replace_windows_clock": False,     # ⭐ جایگزینی کامل و پوشاندن ساعت پیش‌فرض ویندوز
    "replace_clock_hide_widget": False, # مخفی کردن ویجت دسکتاپ هنگام فعال بودن جایگزین
    "replace_clock_width": 82,          # عرض باکس پوشش‌دهنده ساعت ویندوز (هم‌اندازه ساعت بومی ویندوز)
    "replace_clock_offset": 8,          # فاصله از گوشه راست تسک‌بار
    "replace_clock_bg": "auto",         # تشخیص خودکار رنگ تسک‌بار ویندوز (یا رنگ دلخواه)
    "taskbar_clock": False,         # نمایش ساعت و تاریخ شمسی روی خود نوار تسک‌بار (شناور)
    "taskbar_clock_seconds": False, # نمایش ثانیه در ساعت تسک‌بار
    "taskbar_clock_offset": None,   # مکان ذخیره‌شده ساعت روی تسک‌بار (فاصله از لبه راست)
    "taskbar_button": False,        # نمایش دکمه/آیکون برنامه در تسک‌بار
    "snap_side": "right",           # جهت چسبیدن به لبه صفحه در حالت قفل ('right' یا 'left')
    "primary_timezone": "tehran",   # 'tehran' یا 'utc' (تایم اصلی ویجت بدون نمایش +03:30)
    "show_utc": False,              # نمایش ردیف مجزای ساعت و تاریخ UTC در ویجت برای برنامه‌نویسان
    "show_seconds": False,          # نمایش ثانیه در ساعت (همه‌جا: ویجت، UTC و تسک‌بار)
    # پایش IP و قفل روی شهر/IP برای هشدار تغییر لوکیشن
    "ip_monitor_enabled": True,     # نمایش نوار IP و شهر فعلی روی ویجت
    "ip_check_interval": 5,         # بازه بررسی تغییر IP/لوکیشن (ثانیه)
    "ip_lock_enabled": False,       # فعال بودن قفل روی لوکیشن/IP
    "ip_lock_mode": "city",         # 'city' (قفل روی شهر)، 'ip' یا 'both'
    "ip_locked_ip": "",
    "ip_locked_city": "",
    "ip_locked_country": "",
    # سرور محلی AI (HTTP REST + MCP)
    "ai_api_enabled": True,
    "ai_api_port": DEFAULT_API_PORT,
}


def format_digits(text: str, use_persian: bool) -> str:
    """تبدیل اعداد انگلیسی به فارسی در صورت فعال بودن گزینه مربوطه"""
    if not use_persian:
        return str(text)
    en = "0123456789"
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return str(text).translate(str.maketrans(en, fa))


class HoverTooltip:
    """
    افکت Hover فوری و نمایش Tooltip شناور همیشه در بالاترین لایه (Topmost)
    هنگام نگه داشتن ماوس روی آیکون‌ها
    """

    def __init__(
        self,
        widget: tk.Widget,
        text_or_fn,
        base_bg_fn,
        base_fg_fn,
        hover_bg: str = "#0284C7",
        hover_fg: str = "#FFFFFF",
        font_family: str = "Vazir",
    ):
        self.widget = widget
        self.text_or_fn = text_or_fn
        self.base_bg_fn = base_bg_fn
        self.base_fg_fn = base_fg_fn
        self.hover_bg = hover_bg
        self.hover_fg = hover_fg
        self.font_family = font_family
        self.tip_win: tk.Toplevel | None = None
        self._after_id: str | None = None
        self.is_hovered = False

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_press, add="+")

    def _on_enter(self, event=None):
        self.is_hovered = True
        try:
            self.widget.configure(bg=self.hover_bg, fg=self.hover_fg)
        except Exception:
            pass
        self._cancel_timer()
        self._after_id = self.widget.after(90, self._show_tip)

    def _on_leave(self, event=None):
        self.is_hovered = False
        self._cancel_timer()
        try:
            self.widget.configure(bg=self.base_bg_fn(), fg=self.base_fg_fn())
        except Exception:
            pass
        self._hide_tip()

    def _on_press(self, event=None):
        self._cancel_timer()
        self._hide_tip()

    def _cancel_timer(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show_tip(self):
        if not self.is_hovered or self.tip_win is not None:
            return
        txt = self.text_or_fn() if callable(self.text_or_fn) else str(self.text_or_fn)
        if not txt:
            return
        try:
            wx = self.widget.winfo_rootx()
            wy = self.widget.winfo_rooty()
            wh = self.widget.winfo_height()

            win = tk.Toplevel(self.widget)
            self.tip_win = win
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="#0F172A")

            frm = tk.Frame(
                win,
                bg="#0F172A",
                highlightbackground="#38BDF8",
                highlightthickness=1,
                padx=8,
                pady=4,
            )
            frm.pack()
            lbl = tk.Label(
                frm,
                text=txt,
                font=(self.font_family, 8, "bold"),
                fg="#F8FAFC",
                bg="#0F172A",
            )
            lbl.pack()

            win.update_idletasks()
            tw = win.winfo_reqwidth()
            th = win.winfo_reqheight()
            ml, mt, mr, mb = get_monitor_work_area_at(wx, wy, win)

            # نمایش در بالای آیکون یا پایین آیکون به‌گونه‌ای که در مانیتور فعلی کامل دیده شود
            pos_x = wx - (tw // 3)
            if pos_x + tw > mr - 8:
                pos_x = mr - tw - 8
            pos_x = max(ml + 8, pos_x)

            if wy - th - 6 >= mt + 8:
                pos_y = wy - th - 6
            else:
                pos_y = min(mb - th - 8, wy + wh + 6)

            win.geometry(f"+{int(pos_x)}+{int(pos_y)}")
            hide_from_taskbar(win)
            apply_z_order_and_clickthrough(win, "topmost", click_through=True)
        except Exception:
            self._hide_tip()

    def _hide_tip(self):
        if self.tip_win is not None:
            try:
                self.tip_win.destroy()
            except Exception:
                pass
            self.tip_win = None


class PersianClockWidget:
    BASE_MIN_W = 250
    BASE_CALENDAR_W = 310
    BASE_CALENDAR_H = 385

    LOCK_BTN_SIZE = 24
    LOCK_OFFSET_X = 8
    LOCK_OFFSET_Y = 8
    GAP = 8

    def __init__(self):
        enable_dpi_awareness()
        register_bundled_fonts()

        self.config = self._load_config()
        if self.config.get("z_mode") == "overlay_locked":
            self.config["z_mode"] = "topmost"
            self.config["locked"] = True

        # پنجره ریشه مخفی (بدون هیچ آیکونی در Taskbar)
        self.root = tk.Tk()
        self.root.title("PersianClockHiddenRoot")
        self.root.attributes("-alpha", 0.0)
        self.root.withdraw()

        sys_fams = set(tkfont.families())
        if self.config["font_family"] not in sys_fams:
            for candidate in ("Vazir", "B Yekan+", "A Iranian Sans", "Tahoma"):
                if candidate in sys_fams:
                    self.config["font_family"] = candidate
                    break
        if self.config["clock_font_family"] not in sys_fams:
            for candidate in ("Vazir", "B Yekan+", "A Iranian Sans", "Segoe UI Semibold", "Tahoma"):
                if candidate in sys_fams:
                    self.config["clock_font_family"] = candidate
                    break

        ico_path = get_resource_path(os.path.join("assets", "icons", "app_icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(default=ico_path)
            except Exception:
                pass

        self.alarm_store = AlarmStore(ALARMS_PATH)

        today = get_today_info(CUSTOM_OCCASIONS_PATH)
        self.current_jy = today["jy"]
        self.current_jm = today["jm"]
        self.current_jd = today["jd"]

        self.view_jy = today["jy"]
        self.view_jm = today["jm"]
        self.selected_day_info = today

        self._computed_w = self.BASE_MIN_W
        self._computed_h = 118
        self._toast_text = ""

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        self._is_minimized = False
        self._unlocked_x = self.config.get("x")
        self._unlocked_y = self.config.get("y")
        self._tooltips: list[HoverTooltip] = []

        self.widget_win: tk.Toplevel | None = None
        self.lock_win: tk.Toplevel | None = None
        self.cal_win: tk.Toplevel | None = None
        self.dev_popup_win: tk.Toplevel | None = None
        self.settings_win: tk.Toplevel | None = None
        self.alarm_win: AlarmManagerWindow | None = None
        self.custom_occ_win: tk.Toplevel | None = None
        self.ip_win: tk.Toplevel | None = None
        self.dev_ai_hub: DevAiHubWindow | None = None

        self._pomodoro_end_ts: float | None = None
        self._pomodoro_label: str = ""

        self._ip_info: dict = {}
        self._ip_fetch_inflight = False
        self._ip_alert_active = False
        self._ip_last_alert_key = ""
        self._ip_alert_popup: AnimatedBellPopup | None = None
        self.ip_history_store = IpHistoryStore(
            os.path.join(get_data_dir(), "ip_history.json"),
            retention_days=3,
        )

        self._build_compact_ui()
        self._build_lock_badge_window()
        self._build_calendar_window()
        self._build_context_menu()
        self._build_dev_copy_menu()

        self._init_position()
        self.root.after(60, self._apply_all_styles)

        self.tray = SystemTrayIcon(
            tooltip=self._format_tray_tooltip(today),
            on_left_click=self._on_tray_left_click,
            on_right_click=self._on_tray_right_click,
        )
        self.tray.start()

        self.taskbar_clock: TaskbarClockOverlay | None = None
        self.taskbar_proxy: TaskbarButtonProxy | None = None
        self.clock_replacer: WindowsClockReplacer | None = None
        self.root.after(300, self.sync_taskbar_features)

        self._update_clock_loop()
        self._keep_z_order_loop()
        self.root.after(1200, self._ip_monitor_loop)

        self.local_api = LocalWidgetApiServer(
            self,
            port=int(self.config.get("ai_api_port", DEFAULT_API_PORT)),
        )
        if self.config.get("ai_api_enabled", True):
            self.local_api.start()

    # ------------------------------------------------------------------
    # نمایش در تسک‌بار (ساعت روی تسک‌بار + دکمه برنامه در تسک‌بار)
    # ------------------------------------------------------------------
    def format_digits_public(self, text: str, use_fa: bool) -> str:
        return format_digits(text, use_fa)

    def sync_taskbar_features(self):
        """فعال/غیرفعال کردن جایگزین ساعت ویندوز، ساعت روی تسک‌بار و دکمه تسک‌بار بر اساس تنظیمات"""
        want_replacer = bool(self.config.get("replace_windows_clock", False))
        want_clock = bool(self.config.get("taskbar_clock", False))
        want_btn = bool(self.config.get("taskbar_button", False))
        hide_desktop = bool(self.config.get("replace_clock_hide_widget", False)) and want_replacer

        # ۱. جایگزین کامل ساعت و تاریخ ویندوز
        if want_replacer and self.clock_replacer is None:
            self.clock_replacer = WindowsClockReplacer(self)
            self.clock_replacer.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))
        elif not want_replacer and self.clock_replacer is not None:
            self.clock_replacer.destroy()
            self.clock_replacer = None

        # ۲. ساعت و تاریخ شناور روی تسک‌بار
        if want_clock and self.taskbar_clock is None:
            self.taskbar_clock = TaskbarClockOverlay(self)
            self.taskbar_clock.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))
        elif not want_clock and self.taskbar_clock is not None:
            self.taskbar_clock.destroy()
            self.taskbar_clock = None

        # ۳. دکمه/آیکون برنامه در تسک‌بار
        if want_btn and self.taskbar_proxy is None:
            self.taskbar_proxy = TaskbarButtonProxy(self)
        elif not want_btn and self.taskbar_proxy is not None:
            self.taskbar_proxy.destroy()
            self.taskbar_proxy = None

        # ۴. مدیریت نمایش/مخفی‌سازی ویجت دسکتاپ بر اساس تنظیمات جایگزینی
        if hide_desktop:
            if self.widget_win and self.widget_win.winfo_viewable():
                self.widget_win.withdraw()
            if self.lock_win and self.lock_win.winfo_viewable():
                self.lock_win.withdraw()
        else:
            if not getattr(self, "_is_minimized", False):
                if self.widget_win and not self.widget_win.winfo_viewable():
                    self.widget_win.deiconify()
                if self.lock_win and not self.lock_win.winfo_viewable() and self.config.get("locked"):
                    self.lock_win.deiconify()

        for var_name, key in (
            ("_settings_tb_clock_var", "taskbar_clock"),
            ("_settings_tb_btn_var", "taskbar_button"),
            ("_settings_replace_clock_var", "replace_windows_clock"),
            ("_settings_hide_widget_var", "replace_clock_hide_widget"),
        ):
            var = getattr(self, var_name, None)
            if var is not None:
                try:
                    var.set(bool(self.config.get(key, False)))
                except Exception:
                    pass

    def _toggle_taskbar_setting(self, key: str):
        self.config[key] = not self.config.get(key, False)
        self._save_config()
        self.sync_taskbar_features()

    def minimize_widget(self):
        """مخفی کردن ویجت از صفحه دسکتاپ و تسک‌بار؛ فقط در Hidden Icons (سینی سیستم)"""
        self._is_minimized = True
        self._close_dev_popup_window()
        if self.widget_win:
            self.widget_win.withdraw()
        if self.lock_win:
            self.lock_win.withdraw()
        if self.cal_win:
            self.cal_win.withdraw()
        # هنگام مینیمایز یا بستن، هیچ آیکونی در تسک‌بار نمایش داده نشود (فقط در Hidden Icons بماند)
        if self.taskbar_proxy is not None:
            self.taskbar_proxy.destroy()
            self.taskbar_proxy = None
        info = get_today_info(CUSTOM_OCCASIONS_PATH)
        if getattr(self, "taskbar_clock", None) is not None:
            try:
                self.taskbar_clock.refresh(info)
            except Exception:
                pass
        if getattr(self, "clock_replacer", None) is not None:
            try:
                self.clock_replacer.refresh(info)
            except Exception:
                pass

    def restore_widget(self):
        """نمایش مجدد ویجت روی صفحه دسکتاپ"""
        self._is_minimized = False
        if self.widget_win:
            self.widget_win.deiconify()
            self.widget_win.lift()
        if self.lock_win:
            self.lock_win.deiconify()
            self.lock_win.lift()
        self._position_lock_window()
        self._apply_all_styles()
        self.sync_taskbar_features()

    def on_taskbar_clicked(self):
        """کلیک روی ساعت تسک‌بار یا دکمه تسک‌بار: بازیابی از مینیمایز یا باز/بسته کردن تقویم"""
        now_ts = time.monotonic()
        if now_ts - getattr(self, "_last_tb_click_ts", 0.0) < 0.22:
            return
        self._last_tb_click_ts = now_ts

        hide_desktop = (
            bool(self.config.get("replace_windows_clock", False))
            and bool(self.config.get("replace_clock_hide_widget", False))
        )
        if self._is_minimized:
            if not hide_desktop:
                self.restore_widget()
                return
            self._is_minimized = False

        if not hide_desktop:
            if self.widget_win and not self.widget_win.winfo_viewable():
                self.widget_win.deiconify()
            if self.lock_win and not self.lock_win.winfo_viewable() and self.config.get("locked"):
                self.lock_win.deiconify()

        self._toggle_calendar(None)
        if self.config.get("calendar_expanded") and self.cal_win:
            self.cal_win.lift()

    def show_menu_at_pointer(self):
        self._populate_context_menu()
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _get_btn_base_bg(self) -> str:
        return "#161E2E" if not self.config.get("transparent_bg", False) else "#141821"

    def _attach_hover(
        self,
        widget: tk.Widget,
        tooltip_text,
        base_fg_fn,
        hover_bg: str = "#0284C7",
        hover_fg: str = "#FFFFFF",
        base_bg_fn=None,
    ):
        tip = HoverTooltip(
            widget=widget,
            text_or_fn=tooltip_text,
            base_bg_fn=base_bg_fn or self._get_btn_base_bg,
            base_fg_fn=base_fg_fn,
            hover_bg=hover_bg,
            hover_fg=hover_fg,
            font_family=self.config.get("font_family", "Vazir"),
        )
        self._tooltips.append(tip)

    def _format_tray_tooltip(self, info: dict) -> str:
        base = f"{info['time_str']} | {info['date_text']}"
        if info.get("has_occasion") and info.get("occasion"):
            return f"{base} - {info['occasion']}"
        return base

    def _load_config(self) -> dict:
        cfg = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
            except Exception:
                pass
        return cfg

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @property
    def compact_w(self) -> int:
        return self._computed_w

    @property
    def compact_h(self) -> int:
        return self._computed_h

    @property
    def calendar_w(self) -> int:
        scale = max(80, min(150, int(self.config.get("widget_scale", 100)))) / 100.0
        return int(self.BASE_CALENDAR_W * scale)

    @property
    def calendar_h(self) -> int:
        scale = max(80, min(150, int(self.config.get("widget_scale", 100)))) / 100.0
        return int(self.BASE_CALENDAR_H * scale)

    def _build_compact_ui(self):
        self.widget_win = tk.Toplevel(self.root)
        self.widget_win.title("ویجت ساعت و تقویم")
        self.widget_win.overrideredirect(True)
        self.widget_win.protocol("WM_DELETE_WINDOW", self.minimize_widget)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_widget)

        bg = TRANSPARENT_KEY if self.config["transparent_bg"] else self.config["bg_color"]
        self.widget_win.configure(bg=bg)

        self.main_frame = tk.Frame(
            self.widget_win,
            bg=bg,
            highlightbackground=self.config["border_color"] if not self.config["transparent_bg"] else bg,
            highlightthickness=0 if self.config["transparent_bg"] else 1,
        )
        self.main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.main_frame,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._toolbar_seps: list[tk.Widget] = []

        # نوار کوچک کنترل پنجره در بالا-چپ (کنار دکمه قفل) تا عرض ویجت کشیده نشود
        self.win_controls_container = tk.Frame(
            self.canvas,
            bg="#161E2E",
            highlightbackground="#2A364F",
            highlightthickness=1,
            padx=2,
            pady=1,
        )

        # داک فشرده و دو ردیفه ابزارها در پایین ویجت (ردیف اول: تقویم و رویدادها | ردیف دوم: ابزارهای زمان و کدنویسی)
        self.btn_container = tk.Frame(
            self.canvas,
            bg="#161E2E",
            highlightbackground="#2A364F",
            highlightthickness=1,
            padx=5,
            pady=3,
        )
        self._dock_row1 = tk.Frame(self.btn_container, bg="#161E2E")
        self._dock_row1.pack(side="top", fill="x")
        self._dock_hdiv = tk.Frame(self.btn_container, bg="#243047", height=1)
        self._dock_hdiv.pack(side="top", fill="x", padx=2, pady=2)
        self._dock_row2 = tk.Frame(self.btn_container, bg="#161E2E")
        self._dock_row2.pack(side="top", fill="x")

        def _add_tb_sep(parent):
            sep = tk.Label(
                parent,
                text="│",
                font=("Segoe UI", 8),
                fg="#2D3B55",
                bg="#161E2E",
                padx=1,
            )
            sep.pack(side="left")
            self._toolbar_seps.append(sep)

        # ── ردیف اول داک: تقویم و رویدادها ──
        # ۱. دکمه باز/بسته کردن تقویم (Extend)
        self.extend_btn = tk.Label(
            self._dock_row1,
            text="📅 تقویم",
            font=(self.config["font_family"], 8, "bold"),
            fg=self.config["accent_color"],
            bg="#161E2E",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.extend_btn.pack(side="left", expand=True, fill="x", padx=(0, 1))
        self.extend_btn.bind("<Button-1>", self._toggle_calendar)
        self._attach_hover(
            self.extend_btn,
            lambda: "بستن تقویم ماهانه" if self.config.get("calendar_expanded") else "نمایش تقویم ماهانه و مناسبت‌ها",
            base_fg_fn=lambda: self.config.get("accent_color", "#38BDF8"),
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
        )
        _add_tb_sep(self._dock_row1)

        # ۲. دکمه مدیریت رویدادها و آلارم‌ها
        self.alarm_btn = tk.Label(
            self._dock_row1,
            text="⏰ رویداد",
            font=(self.config["font_family"], 8, "bold"),
            fg="#FBBF24",
            bg="#161E2E",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.alarm_btn.pack(side="left", expand=True, fill="x", padx=(1, 1))
        self.alarm_btn.bind("<Button-1>", lambda e: (self.open_alarm_manager(), "break")[1])
        self._attach_hover(
            self.alarm_btn,
            "مدیریت رویدادها و آلارم‌ها (تقویم چندانتخابی)",
            base_fg_fn=lambda: "#FBBF24",
            hover_bg="#D97706",
            hover_fg="#FFFFFF",
        )
        _add_tb_sep(self._dock_row1)

        # ۳. دکمه سریع مدیریت مناسبت‌های شخصی و تولدها
        self.occ_btn = tk.Label(
            self._dock_row1,
            text="🎂 تولد",
            font=(self.config["font_family"], 8, "bold"),
            fg="#F472B6",
            bg="#161E2E",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.occ_btn.pack(side="left", expand=True, fill="x", padx=(1, 0))
        self.occ_btn.bind("<Button-1>", lambda e: (self.open_custom_occasions_manager(), "break")[1])
        self._attach_hover(
            self.occ_btn,
            "ثبت تولد دوستان و مناسبت‌های شخصی + آلارم روز قبل",
            base_fg_fn=lambda: "#F472B6",
            hover_bg="#DB2777",
            hover_fg="#FFFFFF",
        )

        # ── ردیف دوم داک: ابزارهای زمان و برنامه‌نویسی ──
        # ۴. دکمه کپی ۱۰ فرمت زمان برنامه‌نویسی برای API + GUID
        self.copy_time_btn = tk.Label(
            self._dock_row2,
            text="📋 کپی زمان",
            font=(self.config["font_family"], 8, "bold"),
            fg="#A7F3D0",
            bg="#161E2E",
            padx=5,
            pady=2,
            cursor="hand2",
        )
        self.copy_time_btn.pack(side="left", expand=True, fill="x", padx=(0, 1))
        self.copy_time_btn.bind("<Button-1>", self._toggle_dev_popup_window)
        self._attach_hover(
            self.copy_time_btn,
            "کپی زمان (۱۰ فرمت API: تاریخ+ساعت / تاریخ جدا / ساعت جدا) + GUID",
            base_fg_fn=lambda: "#A7F3D0",
            hover_bg="#059669",
            hover_fg="#FFFFFF",
        )
        _add_tb_sep(self._dock_row2)

        # ۵. دکمه اختصاصی رندر و کپی سریع GUID (UUID v4)
        self.guid_btn = tk.Label(
            self._dock_row2,
            text="GUID",
            font=("Consolas", 8, "bold"),
            fg="#C4B5FD",
            bg="#161E2E",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.guid_btn.pack(side="left", expand=True, fill="x", padx=(1, 1))
        self.guid_btn.bind("<Button-1>", self._quick_copy_guid)
        self.guid_btn.bind("<Button-3>", self._toggle_dev_popup_window)
        self._attach_hover(
            self.guid_btn,
            "کلیک چپ: رندر و کپی فوری GUID جدید | کلیک راست: منوی کامل",
            base_fg_fn=lambda: "#C4B5FD",
            hover_bg="#7C3AED",
            hover_fg="#FFFFFF",
        )
        _add_tb_sep(self._dock_row2)

        # ۵.۵. دکمه ابزارهای هوشمند برنامه‌نویسی و AI (v2.0)
        self.dev_ai_btn = tk.Label(
            self._dock_row2,
            text="⚡ AI",
            font=("Consolas", 8, "bold"),
            fg="#38BDF8",
            bg="#161E2E",
            padx=5,
            pady=2,
            cursor="hand2",
        )
        self.dev_ai_btn.pack(side="left", expand=True, fill="x", padx=(1, 1))
        self.dev_ai_btn.bind("<Button-1>", lambda e: (self.open_dev_ai_hub(), "break")[1])
        self._attach_hover(
            self.dev_ai_btn,
            "ابزارهای v2: دستیار Cron، مبدل Timestamp/JWT، جلسات، پومودورو و سرور AI/MCP",
            base_fg_fn=lambda: "#38BDF8",
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
        )
        _add_tb_sep(self._dock_row2)

        # ۶. دکمه سوییچ سریع تایم‌زون اصلی بین تهران و UTC (بدون نمایش +03:30)
        is_utc_primary = self.config.get("primary_timezone", "tehran") == "utc"
        self.tz_btn = tk.Label(
            self._dock_row2,
            text="🌐 UTC" if is_utc_primary else "🌐 TEH",
            font=("Consolas", 8, "bold"),
            fg="#38BDF8" if is_utc_primary else "#E2E8F0",
            bg="#161E2E",
            padx=5,
            pady=2,
            cursor="hand2",
        )
        self.tz_btn.pack(side="left", expand=True, fill="x", padx=(1, 0))
        self.tz_btn.bind("<Button-1>", self._toggle_primary_timezone)
        self._attach_hover(
            self.tz_btn,
            "تبدیل سریع ساعت اصلی بین تهران و UTC (بدون نمایش +03:30)",
            base_fg_fn=lambda: "#38BDF8" if self.config.get("primary_timezone", "tehran") == "utc" else "#E2E8F0",
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
        )

        # ── نوار کنترل پنجره بالا-چپ (تنظیمات، مینیمایز، بستن) ──
        # ۷. دکمه تنظیمات ظاهری
        self.settings_btn = tk.Label(
            self.win_controls_container,
            text="⚙",
            font=("Segoe UI", 8),
            fg=self.config["date_color"],
            bg="#161E2E",
            padx=4,
            pady=1,
            cursor="hand2",
        )
        self.settings_btn.pack(side="left", padx=(0, 1))
        self.settings_btn.bind("<Button-1>", lambda e: (self.open_settings_window(), "break")[1])
        self._attach_hover(
            self.settings_btn,
            "تنظیمات ظاهری، رنگ، سایز و فونت",
            base_fg_fn=lambda: self.config.get("date_color", "#CBD5E1"),
            hover_bg="#475569",
            hover_fg="#FFFFFF",
        )

        # ۸. دکمه مینیمایز و بستن به Hidden Icons (بدون آیکون در تسک‌بار)
        self.min_btn = tk.Label(
            self.win_controls_container,
            text="🗕",
            font=("Segoe UI", 8, "bold"),
            fg=self.config["date_color"],
            bg="#161E2E",
            padx=4,
            pady=1,
            cursor="hand2",
        )
        self.min_btn.pack(side="left", padx=(1, 1))
        self.min_btn.bind("<Button-1>", lambda e: (self.minimize_widget(), "break")[1])
        self._attach_hover(
            self.min_btn,
            "مینیمایز به Hidden Icons (بدون آیکون در تسک‌بار)",
            base_fg_fn=lambda: self.config.get("date_color", "#CBD5E1"),
            hover_bg="#475569",
            hover_fg="#FFFFFF",
        )

        # ۹. دکمه بستن ویجت (انتقال به Hidden Icons؛ برای خروج کامل از راست‌کلیک سینی سیستم استفاده کنید)
        self.close_btn = tk.Label(
            self.win_controls_container,
            text="✕",
            font=("Segoe UI", 8, "bold"),
            fg="#FCA5A5",
            bg="#161E2E",
            padx=4,
            pady=1,
            cursor="hand2",
        )
        self.close_btn.pack(side="left", padx=(1, 0))
        self.close_btn.bind("<Button-1>", lambda e: (self.minimize_widget(), "break")[1])
        self._attach_hover(
            self.close_btn,
            "بستن ویجت روی دسکتاپ (ارسال به Hidden Icons)",
            base_fg_fn=lambda: "#FCA5A5",
            hover_bg="#DC2626",
            hover_fg="#FFFFFF",
        )

        # ایجاد یک‌باره پنجره‌های نوار کنترل و داک روی Canvas تا در رفرش ثانیه‌ای حذف نشوند و Hover پایدار بماند
        toolbar_x = self.LOCK_OFFSET_X + self.LOCK_BTN_SIZE + 8
        toolbar_y = self.LOCK_OFFSET_Y
        self._win_controls_win_id = self.canvas.create_window(
            toolbar_x,
            toolbar_y,
            window=self.win_controls_container,
            anchor="nw",
            tags="toolbar",
        )
        self._toolbar_win_id = self.canvas.create_window(
            12,
            100,
            window=self.btn_container,
            anchor="nw",
            tags="toolbar",
        )

        # نوار نمایش IP و شهر فعلی + قفل لوکیشن (قابل کلیک برای تنظیمات و قفل)
        self.ip_pill_lbl = tk.Label(
            self.canvas,
            text="🌐 در حال بررسی IP و لوکیشن...",
            font=(self.config["font_family"], 8, "bold"),
            fg="#94A3B8",
            bg="#161E2E",
            highlightbackground="#2A364F",
            highlightthickness=1,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.ip_pill_lbl.bind("<Button-1>", lambda e: (self.open_ip_monitor_window(), "break")[1])
        self._attach_hover(
            self.ip_pill_lbl,
            "کلیک: مشاهده جزئیات IP، قفل روی شهر فعلی و هشدار تغییر لوکیشن",
            base_fg_fn=lambda: self._get_ip_pill_fg(),
            hover_bg="#1E293B",
            hover_fg="#FFFFFF",
        )
        self._ip_pill_win_id = self.canvas.create_window(
            12,
            80,
            window=self.ip_pill_lbl,
            anchor="nw",
            tags="toolbar",
        )

        # بایندینگ درگ و دابل‌کلیک فقط روی بوم و قاب اصلی (نه روی toplevel تا دکمه‌های نوار ابزار را نگیرد)
        for w in (self.main_frame, self.canvas):
            w.bind("<ButtonPress-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_end)
            w.bind("<Button-3>", self._show_context_menu)
            w.bind("<Double-Button-1>", self._toggle_calendar)

    def _quick_copy_guid(self, event=None):
        """تولید و کپی فوری یک GUID (UUID v4) استاندارد با یک کلیک روی دکمه GUID"""
        if self.config.get("locked", False):
            return "break"
        new_guid = str(uuid.uuid4())
        self._copy_to_clipboard(new_guid, f"✓ GUID کپی شد!")
        return "break"

    def _update_tz_btn_appearance(self):
        if hasattr(self, "tz_btn") and self.tz_btn.winfo_exists():
            is_utc = self.config.get("primary_timezone", "tehran") == "utc"
            self.tz_btn.configure(
                text="🌐 UTC" if is_utc else "🌐 TEH",
                fg="#38BDF8" if is_utc else "#E2E8F0",
                bg=self._get_btn_base_bg(),
            )

    def _toggle_primary_timezone(self, event=None):
        """سوییچ سریع ساعت اصلی ویجت بین تهران و UTC (بدون نمایش +03:30)"""
        if event is not None and self.config.get("locked", False):
            return "break"
        cur = self.config.get("primary_timezone", "tehran")
        new_tz = "utc" if cur != "utc" else "tehran"
        self.config["primary_timezone"] = new_tz
        self._save_config()
        self._update_tz_btn_appearance()
        var = getattr(self, "_settings_primary_tz_var", None)
        if var is not None:
            try:
                var.set(new_tz)
            except Exception:
                pass
        self._refresh_display()
        return "break"

    def _toggle_show_utc(self):
        self.config["show_utc"] = not bool(self.config.get("show_utc", False))
        self._save_config()
        var = getattr(self, "_settings_show_utc_var", None)
        if var is not None:
            try:
                var.set(bool(self.config["show_utc"]))
            except Exception:
                pass
        self._refresh_display()

    def _toggle_show_seconds(self):
        new_val = not bool(self.config.get("show_seconds", False))
        self.config["show_seconds"] = new_val
        self.config["taskbar_clock_seconds"] = new_val
        self._save_config()
        var = getattr(self, "_settings_show_seconds_var", None)
        if var is not None:
            try:
                var.set(new_val)
            except Exception:
                pass
        self._refresh_display()

    def _build_lock_badge_window(self):
        self.lock_win = tk.Toplevel(self.root)
        self.lock_win.overrideredirect(True)
        self.lock_win.configure(bg="#1E293B")

        self.lock_frame = tk.Frame(
            self.lock_win,
            bg="#1E293B",
            highlightbackground=self.config["border_color"],
            highlightthickness=1,
        )
        self.lock_frame.pack(fill="both", expand=True)

        self.lock_btn_label = tk.Label(
            self.lock_frame,
            text="🔒" if self.config.get("locked") else "🔓",
            font=("Segoe UI Emoji", 8),
            fg="#FBBF24" if self.config.get("locked") else self.config["accent_color"],
            bg="#1E293B",
            cursor="hand2",
        )
        self.lock_btn_label.pack(fill="both", expand=True)

        self.lock_btn_label.bind("<Button-1>", lambda e: self._toggle_lock())
        self.lock_frame.bind("<Button-1>", lambda e: self._toggle_lock())
        self.lock_btn_label.bind("<Button-3>", self._on_lock_btn_right_click)
        self._attach_hover(
            self.lock_btn_label,
            lambda: "باز کردن قفل ویجت (🔓)" if self.config.get("locked") else "قفل روی صفحه و عبوردهی کلیک (🔒)",
            base_fg_fn=lambda: "#FBBF24" if self.config.get("locked") else self.config.get("accent_color", "#38BDF8"),
            hover_bg="#334155",
            hover_fg="#FDE047",
        )

    def _on_lock_btn_right_click(self, event):
        if not self.config.get("locked", False):
            self._show_context_menu(event)

    def _position_lock_window(self, wx: int | None = None, wy: int | None = None):
        if not self.lock_win or not self.widget_win:
            return
        if wx is None or wy is None:
            self.widget_win.update_idletasks()
            wx = self.widget_win.winfo_x()
            wy = self.widget_win.winfo_y()
        sz = self.LOCK_BTN_SIZE
        lx = int(wx) + self.LOCK_OFFSET_X
        ly = int(wy) + self.LOCK_OFFSET_Y
        self.lock_win.geometry(f"{sz}x{sz}+{lx}+{ly}")

    def _get_dev_copy_data(self) -> dict:
        """محاسبه لحظه‌ای ۱۰ فرمت پرکاربرد تاریخ و ساعت برای API + مقادیر GUID"""
        now_utc = datetime.now(timezone.utc)
        now_teh = now_utc.astimezone(TEHRAN_TZ)
        jy, jm, jd = gregorian_to_jalali(now_teh.year, now_teh.month, now_teh.day)

        ms_teh = now_teh.microsecond // 1000
        ms_utc = now_utc.microsecond // 1000

        fmt_1_utc_iso = f"{now_utc.strftime('%Y-%m-%dT%H:%M:%S')}.{ms_utc:03d}Z"
        fmt_2_teh_iso = f"{now_teh.strftime('%Y-%m-%dT%H:%M:%S')}.{ms_teh:03d}+03:30"
        fmt_3_sql_dt = f"{now_teh.strftime('%Y-%m-%d %H:%M:%S')}.{ms_teh:03d}"
        fmt_4_jalali_dt = f"{jy:04d}/{jm:02d}/{jd:02d} {now_teh.strftime('%H:%M:%S')}.{ms_teh:03d}"

        fmt_5_greg_date = now_teh.strftime("%Y-%m-%d")
        fmt_6_jalali_date = f"{jy:04d}/{jm:02d}/{jd:02d}"

        fmt_7_time_ms = f"{now_teh.strftime('%H:%M:%S')}.{ms_teh:03d}"
        fmt_8_time_std = now_teh.strftime("%H:%M:%S")

        unix_ms = int(now_utc.timestamp() * 1000)
        unix_sec = int(now_utc.timestamp())
        fmt_9_unix_ms = str(unix_ms)
        fmt_10_unix_sec = str(unix_sec)

        new_guid_lower = str(uuid.uuid4())
        new_guid_upper = new_guid_lower.upper()
        new_guid_no_dash = new_guid_lower.replace("-", "")
        empty_guid = "00000000-0000-0000-0000-000000000000"

        json_payload = json.dumps(
            {
                "utc_iso": fmt_1_utc_iso,
                "tehran_iso": fmt_2_teh_iso,
                "sql_datetime": fmt_3_sql_dt,
                "jalali_datetime": fmt_4_jalali_dt,
                "date_gregorian": fmt_5_greg_date,
                "date_jalali": fmt_6_jalali_date,
                "time_ms": fmt_7_time_ms,
                "time_std": fmt_8_time_std,
                "unix_ms": unix_ms,
                "unix_sec": unix_sec,
                "guid": new_guid_lower,
            },
            ensure_ascii=False,
        )

        return {
            "fmt_1_utc_iso": fmt_1_utc_iso,
            "fmt_2_teh_iso": fmt_2_teh_iso,
            "fmt_3_sql_dt": fmt_3_sql_dt,
            "fmt_4_jalali_dt": fmt_4_jalali_dt,
            "fmt_5_greg_date": fmt_5_greg_date,
            "fmt_6_jalali_date": fmt_6_jalali_date,
            "fmt_7_time_ms": fmt_7_time_ms,
            "fmt_8_time_std": fmt_8_time_std,
            "fmt_9_unix_ms": fmt_9_unix_ms,
            "fmt_10_unix_sec": fmt_10_unix_sec,
            "new_guid_lower": new_guid_lower,
            "new_guid_upper": new_guid_upper,
            "new_guid_no_dash": new_guid_no_dash,
            "empty_guid": empty_guid,
            "json_payload": json_payload,
        }

    def _toggle_dev_popup_window(self, event=None):
        """
        نمایش پنجره شناور اختصاصی کپی زمان برنامه‌نویسی (۱۰ فرمت API) و GUID
        با فاصله استاندارد از ویجت و در بالاترین لایه (Topmost) تا هرگز زیر ویجت نرود.
        """
        if self.config.get("locked", False):
            return "break"
        if self.dev_popup_win and self.dev_popup_win.winfo_exists():
            self._close_dev_popup_window()
            return "break"
        # جلوگیری از باز شدن مجدد در همان کلیک وقتی FocusOut پنجره را تازه بسته است
        if time.monotonic() - getattr(self, "_dev_popup_closed_ts", 0.0) < 0.28:
            return "break"

        d = self._get_dev_copy_data()
        font_fa = self.config.get("font_family", "Vazir")

        win = tk.Toplevel(self.root)
        self.dev_popup_win = win
        win.title("ابزار کپی زمان API و GUID")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#0F172A")

        outer = tk.Frame(
            win,
            bg="#0F172A",
            highlightbackground="#38BDF8",
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        outer.pack(fill="both", expand=True)

        # هدر پنل
        hdr = tk.Frame(outer, bg="#0F172A")
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(
            hdr,
            text="📋 کپی سریع تاریخ، ساعت API و تولید GUID",
            font=(font_fa, 9, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
        ).pack(side="right")

        close_lbl = tk.Label(
            hdr,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            fg="#94A3B8",
            bg="#1E293B",
            padx=6,
            pady=1,
            cursor="hand2",
        )
        close_lbl.pack(side="left")
        close_lbl.bind("<Button-1>", lambda e: self._close_dev_popup_window())
        close_lbl.bind("<Enter>", lambda e: close_lbl.configure(bg="#EF4444", fg="#FFFFFF"))
        close_lbl.bind("<Leave>", lambda e: close_lbl.configure(bg="#1E293B", fg="#94A3B8"))

        def add_section_title(txt: str):
            tk.Label(
                outer,
                text=txt,
                font=(font_fa, 8, "bold"),
                fg="#FBBF24",
                bg="#0F172A",
                anchor="e",
            ).pack(fill="x", pady=(4, 2))

        def add_copy_row(title_txt: str, value_txt: str, copy_fn_or_val, toast_msg: str = "✓ کپی شد!"):
            row = tk.Frame(outer, bg="#1E293B", padx=6, pady=3, cursor="hand2")
            row.pack(fill="x", pady=1)

            val_lbl = tk.Label(
                row,
                text=value_txt,
                font=("Consolas", 8, "bold"),
                fg="#38BDF8",
                bg="#1E293B",
                anchor="w",
                cursor="hand2",
            )
            val_lbl.pack(side="left")

            t_lbl = tk.Label(
                row,
                text=title_txt,
                font=(font_fa, 8),
                fg="#E2E8F0",
                bg="#1E293B",
                anchor="e",
                cursor="hand2",
            )
            t_lbl.pack(side="right")

            def on_click(e=None):
                val = copy_fn_or_val() if callable(copy_fn_or_val) else copy_fn_or_val
                self._copy_to_clipboard(val, toast_msg)
                self._close_dev_popup_window()

            def on_enter(e=None):
                row.configure(bg="#0284C7")
                val_lbl.configure(bg="#0284C7", fg="#FFFFFF")
                t_lbl.configure(bg="#0284C7", fg="#FFFFFF")

            def on_leave(e=None):
                row.configure(bg="#1E293B")
                val_lbl.configure(bg="#1E293B", fg="#38BDF8")
                t_lbl.configure(bg="#1E293B", fg="#E2E8F0")

            for w in (row, val_lbl, t_lbl):
                w.bind("<Button-1>", on_click)
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

        # بخش اول: تولید و کپی GUID (UUID v4)
        add_section_title("🔑 تولید و کپی GUID (UUID v4):")
        add_copy_row("🎲 رندر GUID جدید (استاندارد)", d["new_guid_lower"], lambda: str(uuid.uuid4()), "✓ GUID کپی شد!")
        add_copy_row("🎲 رندر GUID (حروف بزرگ)", d["new_guid_upper"], lambda: str(uuid.uuid4()).upper(), "✓ GUID (Upper) کپی شد!")
        add_copy_row("🎲 رندر GUID (بدون خط تیره)", d["new_guid_no_dash"], lambda: uuid.uuid4().hex, "✓ GUID (Hex) کپی شد!")
        add_copy_row("🎲 کپی Empty GUID (صفر)", d["empty_guid"], d["empty_guid"], "✓ Empty GUID کپی شد!")

        # بخش دوم: ۱۰ فرمت پرکاربرد تاریخ و ساعت برای API
        add_section_title("📅+🕒 تاریخ و ساعت با هم (Date & Time - API):")
        add_copy_row("۱. ISO-8601 UTC (با میلی‌ثانیه)", d["fmt_1_utc_iso"], d["fmt_1_utc_iso"])
        add_copy_row("۲. ISO-8601 تهران (با میلی‌ثانیه)", d["fmt_2_teh_iso"], d["fmt_2_teh_iso"])
        add_copy_row("۳. SQL / API DateTime", d["fmt_3_sql_dt"], d["fmt_3_sql_dt"])
        add_copy_row("۴. تاریخ و ساعت شمسی (با ms)", d["fmt_4_jalali_dt"], d["fmt_4_jalali_dt"])

        add_section_title("📅 فقط تاریخ جدا (Date Only):")
        add_copy_row("۵. فقط تاریخ میلادی (Gregorian)", d["fmt_5_greg_date"], d["fmt_5_greg_date"])
        add_copy_row("۶. فقط تاریخ شمسی (Jalali)", d["fmt_6_jalali_date"], d["fmt_6_jalali_date"])

        add_section_title("🕒 فقط ساعت جدا (Time Only) و تایم‌استمپ:")
        add_copy_row("۷. فقط ساعت + میلی‌ثانیه (تهران)", d["fmt_7_time_ms"], d["fmt_7_time_ms"])
        add_copy_row("۸. فقط ساعت استاندارد (HH:MM:SS)", d["fmt_8_time_std"], d["fmt_8_time_std"])
        add_copy_row("۹. Unix Timestamp (میلی‌ثانیه ms)", d["fmt_9_unix_ms"], d["fmt_9_unix_ms"])
        add_copy_row("۱۰. Unix Timestamp (ثانیه sec)", d["fmt_10_unix_sec"], d["fmt_10_unix_sec"])

        add_copy_row("📦 کپی همه موارد به صورت JSON", "{ ... }", d["json_payload"], "✓ JSON کپی شد!")

        win.update_idletasks()
        pw = max(370, win.winfo_reqwidth())
        ph = win.winfo_reqheight()

        wx = self.widget_win.winfo_x()
        wy = self.widget_win.winfo_y()
        ww = self.compact_w
        wh = self.compact_h
        ml, mt, mr, mb = get_monitor_work_area_at(wx + ww // 2, wy + wh // 2, self.root)

        # قرارگیری با فاصله ۱۲ پیکسلی در پایین یا بالای ویجت (بدون همپوشانی با خود ویجت)
        px = wx + ww - pw
        px = max(ml + 10, min(px, mr - pw - 10))
        if wy + wh + 12 + ph <= mb - 8:
            py = wy + wh + 12
        elif wy - ph - 12 >= mt + 10:
            py = wy - ph - 12
        else:
            # در کنار ویجت با فاصله ۱۲ پیکسل
            if wx - pw - 12 >= ml + 10:
                px = wx - pw - 12
            else:
                px = min(mr - pw - 10, wx + ww + 12)
            py = max(mt + 10, min(wy, mb - ph - 8))

        win.geometry(f"{pw}x{ph}+{int(px)}+{int(py)}")
        hide_from_taskbar(win)
        apply_rounded_corners(win, pw, ph, radius=12, enabled=True)
        apply_z_order_and_clickthrough(win, "topmost", click_through=False)
        win.lift()
        win.bind("<Escape>", lambda e: self._close_dev_popup_window())
        win.after(60, lambda: win.winfo_exists() and win.focus_force())
        win.after(180, lambda: win.winfo_exists() and win.bind("<FocusOut>", self._on_dev_popup_focus_out))
        return "break"

    def _on_dev_popup_focus_out(self, event=None):
        if self.dev_popup_win is None or not self.dev_popup_win.winfo_exists():
            return
        try:
            foc = self.root.focus_get()
            if foc is not None and str(foc).startswith(str(self.dev_popup_win)):
                return
        except Exception:
            pass
        self._dev_popup_closed_ts = time.monotonic()
        self._close_dev_popup_window()

    def _close_dev_popup_window(self):
        if self.dev_popup_win is not None:
            self._dev_popup_closed_ts = time.monotonic()
            try:
                self.dev_popup_win.destroy()
            except Exception:
                pass
            self.dev_popup_win = None

    def _build_dev_copy_menu(self):
        """منوی آبشاری کپی زمان و GUID برای منوی راست‌کلیک System Tray"""
        self.copy_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#0F172A",
            fg="#F8FAFC",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            font=("Consolas", 9),
        )

    def _populate_dev_copy_menu(self):
        self.copy_menu.delete(0, "end")
        d = self._get_dev_copy_data()

        self.copy_menu.add_command(label="─── 🔑 GUID / UUID v4 Generator ───", state="disabled")
        self.copy_menu.add_command(
            label=f"🎲 Render & Copy GUID (v4):   {d['new_guid_lower']}",
            command=lambda: self._copy_to_clipboard(str(uuid.uuid4()), "✓ GUID کپی شد!"),
        )
        self.copy_menu.add_command(
            label=f"🎲 Render GUID (UPPERCASE):   {d['new_guid_upper']}",
            command=lambda: self._copy_to_clipboard(str(uuid.uuid4()).upper(), "✓ GUID (Upper) کپی شد!"),
        )
        self.copy_menu.add_command(
            label=f"🎲 Render GUID (No Hyphens):  {d['new_guid_no_dash']}",
            command=lambda: self._copy_to_clipboard(uuid.uuid4().hex, "✓ GUID (Hex) کپی شد!"),
        )
        self.copy_menu.add_command(
            label=f"🎲 Copy Empty GUID (0000...): {d['empty_guid']}",
            command=lambda: self._copy_to_clipboard(d["empty_guid"], "✓ Empty GUID کپی شد!"),
        )

        self.copy_menu.add_separator()
        self.copy_menu.add_command(label="─── 📅+🕒 Date & Time (API / ISO / DB) ───", state="disabled")
        for lbl, val in [
            (f"1. ISO-8601 UTC (ms):     {d['fmt_1_utc_iso']}", d["fmt_1_utc_iso"]),
            (f"2. ISO-8601 Tehran (ms):  {d['fmt_2_teh_iso']}", d["fmt_2_teh_iso"]),
            (f"3. SQL / API DateTime:    {d['fmt_3_sql_dt']}", d["fmt_3_sql_dt"]),
            (f"4. Jalali DateTime (ms):  {d['fmt_4_jalali_dt']}", d["fmt_4_jalali_dt"]),
        ]:
            self.copy_menu.add_command(label=lbl, command=lambda v=val: self._copy_to_clipboard(v))

        self.copy_menu.add_separator()
        self.copy_menu.add_command(label="─── 📅 Date Only (فقط تاریخ جدا) ───", state="disabled")
        for lbl, val in [
            (f"5. Date Only (Gregorian): {d['fmt_5_greg_date']}", d["fmt_5_greg_date"]),
            (f"6. Date Only (Jalali):    {d['fmt_6_jalali_date']}", d["fmt_6_jalali_date"]),
        ]:
            self.copy_menu.add_command(label=lbl, command=lambda v=val: self._copy_to_clipboard(v))

        self.copy_menu.add_separator()
        self.copy_menu.add_command(label="─── 🕒 Time Only & Unix Epoch ───", state="disabled")
        for lbl, val in [
            (f"7. Time Only + ms (Teh):  {d['fmt_7_time_ms']}", d["fmt_7_time_ms"]),
            (f"8. Time Only (HH:MM:SS):  {d['fmt_8_time_std']}", d["fmt_8_time_std"]),
            (f"9.  Unix Timestamp (ms):  {d['fmt_9_unix_ms']}", d["fmt_9_unix_ms"]),
            (f"10. Unix Timestamp (sec): {d['fmt_10_unix_sec']}", d["fmt_10_unix_sec"]),
        ]:
            self.copy_menu.add_command(label=lbl, command=lambda v=val: self._copy_to_clipboard(v))

        self.copy_menu.add_separator()
        self.copy_menu.add_command(
            label="📦 Copy All as JSON Object",
            command=lambda v=d["json_payload"]: self._copy_to_clipboard(v, "✓ JSON کپی شد!"),
        )

    def _copy_to_clipboard(self, text_val: str, toast_msg: str = "✓ کپی شد!"):
        self.root.clipboard_clear()
        self.root.clipboard_append(text_val)
        self.root.update()
        self._show_toast(toast_msg)

    def _show_toast(self, msg: str):
        self._toast_text = msg
        self._refresh_display()

        def _clear():
            self._toast_text = ""
            self._refresh_display()

        self.root.after(1600, _clear)

    def _build_calendar_window(self):
        self.cal_win = tk.Toplevel(self.root)
        self.cal_win.overrideredirect(True)
        bg = self.config["bg_color"]
        self.cal_win.configure(bg=bg)

        self.cal_frame = tk.Frame(
            self.cal_win,
            bg=bg,
            highlightbackground=self.config["border_color"],
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        self.cal_frame.pack(fill="both", expand=True)

        self.cal_header = tk.Frame(self.cal_frame, bg=bg)
        self.cal_header.pack(fill="x", pady=(0, 6))

        self.next_month_btn = tk.Label(
            self.cal_header,
            text="‹",
            font=("Segoe UI", 13, "bold"),
            fg=self.config["clock_color"],
            bg="#1E2638",
            padx=8,
            pady=0,
            cursor="hand2",
        )
        self.next_month_btn.pack(side="left")
        self.next_month_btn.bind("<Button-1>", lambda e: self._change_month(1))
        self._attach_hover(
            self.next_month_btn,
            "ماه بعد",
            base_fg_fn=lambda: self.config.get("clock_color", "#F8FAFC"),
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
            base_bg_fn=lambda: "#1E2638",
        )

        self.today_btn = tk.Label(
            self.cal_header,
            text="امروز",
            font=(self.config["font_family"], 8, "bold"),
            fg=self.config["accent_color"],
            bg="#1E2638",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.today_btn.pack(side="left", padx=(4, 0))
        self.today_btn.bind("<Button-1>", lambda e: self._go_to_today())
        self._attach_hover(
            self.today_btn,
            "بازگشت به تاریخ امروز",
            base_fg_fn=lambda: self.config.get("accent_color", "#38BDF8"),
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
            base_bg_fn=lambda: "#1E2638",
        )

        self.prev_month_btn = tk.Label(
            self.cal_header,
            text="›",
            font=("Segoe UI", 13, "bold"),
            fg=self.config["clock_color"],
            bg="#1E2638",
            padx=8,
            pady=0,
            cursor="hand2",
        )
        self.prev_month_btn.pack(side="right")
        self.prev_month_btn.bind("<Button-1>", lambda e: self._change_month(-1))
        self._attach_hover(
            self.prev_month_btn,
            "ماه قبل",
            base_fg_fn=lambda: self.config.get("clock_color", "#F8FAFC"),
            hover_bg="#0284C7",
            hover_fg="#FFFFFF",
            base_bg_fn=lambda: "#1E2638",
        )

        self.cal_title_canvas = tk.Canvas(
            self.cal_header,
            width=150,
            height=26,
            bg=bg,
            highlightthickness=0,
        )
        self.cal_title_canvas.pack(side="right", fill="x", expand=True)

        self.week_header = tk.Frame(self.cal_frame, bg=bg)
        self.week_header.pack(fill="x", pady=(0, 4))
        self.week_canvases: list[tk.Canvas] = []
        for col_idx in range(7):
            c_canvas = tk.Canvas(
                self.week_header,
                width=34,
                height=20,
                bg=bg,
                highlightthickness=0,
            )
            c_canvas.grid(row=0, column=col_idx, sticky="nsew", padx=1)
            self.week_header.grid_columnconfigure(col_idx, weight=1)
            self.week_canvases.append(c_canvas)

        self.days_grid_frame = tk.Frame(self.cal_frame, bg=bg)
        self.days_grid_frame.pack(fill="x", pady=(0, 4))

        self.day_cells: list[tk.Canvas] = []
        for r in range(6):
            self.days_grid_frame.grid_rowconfigure(r, weight=1)
            for c in range(7):
                self.days_grid_frame.grid_columnconfigure(c, weight=1)
                cell = tk.Canvas(
                    self.days_grid_frame,
                    width=34,
                    height=26,
                    bg=bg,
                    highlightthickness=0,
                    cursor="hand2",
                )
                cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                self.day_cells.append(cell)

        self.cal_sep = tk.Frame(self.cal_frame, bg=self.config["border_color"], height=1)
        self.cal_sep.pack(fill="x", pady=(2, 4))

        self.cal_bottom_bar = tk.Frame(self.cal_frame, bg=bg)
        self.cal_bottom_bar.pack(side="bottom", fill="x", pady=(4, 0))

        self.detail_canvas = tk.Canvas(
            self.cal_frame,
            width=260,
            height=54,
            bg=bg,
            highlightthickness=0,
        )
        self.detail_canvas.pack(fill="both", expand=True)

        self.add_event_btn = tk.Label(
            self.cal_bottom_bar,
            text="⏰ + آلارم",
            font=(self.config["font_family"], 8, "bold"),
            fg="#FBBF24",
            bg="#1E2638",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.add_event_btn.pack(side="right")
        self.add_event_btn.bind("<Button-1>", lambda e: self.open_alarm_manager())
        self._attach_hover(
            self.add_event_btn,
            "افزودن یا ویرایش آلارم و رویداد با انتخاب چندروزه",
            base_fg_fn=lambda: "#FBBF24",
            hover_bg="#D97706",
            hover_fg="#FFFFFF",
            base_bg_fn=lambda: "#1E2638",
        )

        self.add_occasion_btn = tk.Label(
            self.cal_bottom_bar,
            text="🎂 + تولد/مناسبت",
            font=(self.config["font_family"], 8, "bold"),
            fg="#F472B6",
            bg="#1E2638",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.add_occasion_btn.pack(side="right", padx=(0, 4))
        self.add_occasion_btn.bind("<Button-1>", lambda e: self.open_custom_occasions_manager())
        self._attach_hover(
            self.add_occasion_btn,
            "ثبت تولد دوستان و مناسبت‌های شخصی روی تقویم + آلارم روز قبل",
            base_fg_fn=lambda: "#F472B6",
            hover_bg="#DB2777",
            hover_fg="#FFFFFF",
            base_bg_fn=lambda: "#1E2638",
        )

        self.cal_copyright_lbl = tk.Label(
            self.cal_bottom_bar,
            text="® Shayan Bamyar",
            font=("Segoe UI", 7, "bold"),
            fg="#64748B",
            bg=bg,
        )
        self.cal_copyright_lbl.pack(side="left")

        self.cal_win.bind("<Button-3>", self._show_context_menu)

        if not self.config.get("calendar_expanded", False):
            self.cal_win.withdraw()

    def _render_calendar_month(self):
        month_data = get_month_calendar(self.view_jy, self.view_jm, CUSTOM_OCCASIONS_PATH)
        use_fa = self.config.get("persian_digits", False)
        bg = self.config["bg_color"]
        font_fa = self.config.get("font_family", "Vazir")

        self.cal_title_canvas.configure(bg=bg)
        self.cal_title_canvas.delete("all")
        self.cal_title_canvas.update_idletasks()
        tw = max(140, self.cal_title_canvas.winfo_width())
        draw_outlined_canvas_text(
            self.cal_title_canvas,
            tw // 2,
            13,
            text=format_digits(month_data["header_title"], use_fa),
            font_spec=(font_fa, 10, "bold"),
            fill=self.config["clock_color"],
            outline="#000000",
        )

        for col_idx, w_canvas in enumerate(self.week_canvases):
            p_idx = 6 - col_idx
            day_short = PERSIAN_WEEK_SHORT[p_idx]
            fg_color = self.config["holiday_color"] if p_idx == 6 else self.config["occasion_color"]
            w_canvas.configure(bg=bg)
            w_canvas.delete("all")
            wc_w = max(34, w_canvas.winfo_width())
            draw_outlined_canvas_text(
                w_canvas,
                wc_w // 2,
                10,
                text=day_short,
                font_spec=(font_fa, 8, "bold"),
                fill=fg_color,
                outline="#000000",
            )

        for cell in self.day_cells:
            cell.configure(bg=bg, cursor="arrow")
            cell.delete("all")
            cell.unbind("<Button-1>")
            cell.unbind("<Enter>")
            cell.unbind("<Leave>")

        first_week_idx = month_data["first_day_week_idx"]

        for day_info in month_data["days"]:
            d = day_info["jd"]
            offset = first_week_idx + (d - 1)
            row = offset // 7
            persian_col = offset % 7
            grid_col = 6 - persian_col
            cell_idx = row * 7 + grid_col
            if cell_idx >= len(self.day_cells):
                continue

            cell = self.day_cells[cell_idx]
            day_str = format_digits(str(d), use_fa)

            user_alarms = self.alarm_store.get_events_for_jalali_day(
                day_info["jy"], day_info["jm"], day_info["jd"], day_info["persian_week_idx"]
            )
            has_any_event = day_info["has_occasion"] or len(user_alarms) > 0

            is_today = (
                day_info["jy"] == self.current_jy
                and day_info["jm"] == self.current_jm
                and day_info["jd"] == self.current_jd
            )
            is_selected = (
                self.selected_day_info
                and day_info["jy"] == self.selected_day_info["jy"]
                and day_info["jm"] == self.selected_day_info["jm"]
                and day_info["jd"] == self.selected_day_info["jd"]
            )

            if is_today:
                cell_bg = "#0369A1"
                cell_fg = "#FFFFFF"
            elif is_selected:
                cell_bg = "#1E293B"
                cell_fg = self.config["holiday_color"] if day_info["is_holiday"] else "#FFFFFF"
            else:
                cell_bg = bg
                cell_fg = self.config["holiday_color"] if day_info["is_holiday"] else self.config["clock_color"]

            cell.configure(bg=cell_bg, cursor="hand2")
            cell_w = max(34, cell.winfo_width())
            cell_h = max(26, cell.winfo_height())
            if is_today or is_selected:
                cell.create_rectangle(
                    1,
                    1,
                    cell_w - 2,
                    cell_h - 2,
                    outline="#38BDF8" if is_today else "#64748B",
                    width=1,
                )
            draw_outlined_canvas_text(
                cell,
                cell_w // 2,
                (cell_h // 2) - 2,
                text=day_str,
                font_spec=(font_fa, 9, "bold" if (is_today or is_selected) else "normal"),
                fill=cell_fg,
                outline="#000000",
            )
            if has_any_event:
                has_bday = "🎂" in (day_info.get("occasion") or "")
                dot_color = "#F472B6" if has_bday else ("#FBBF24" if user_alarms else self.config["accent_color"])
                dx = cell_w // 2
                dy = cell_h - 4
                cell.create_oval(dx - 2, dy - 2, dx + 2, dy + 2, fill=dot_color, outline="#000000")

            cell.bind("<Button-1>", lambda e, info=day_info: self._on_day_clicked(info))
            if not is_today and not is_selected:
                cell.bind("<Enter>", lambda e, c=cell: c.configure(bg="#1E293B"))
                cell.bind("<Leave>", lambda e, c=cell, b=cell_bg: c.configure(bg=b))

        self._update_selected_day_panel()

    def _on_day_clicked(self, day_info: dict):
        if self.config.get("locked", False):
            return
        self.selected_day_info = day_info
        self._render_calendar_month()

    def _update_selected_day_panel(self):
        info = self.selected_day_info
        if not info:
            return
        use_fa = self.config.get("persian_digits", False)
        bg = self.config["bg_color"]
        font_fa = self.config.get("font_family", "Vazir")

        self.detail_canvas.configure(bg=bg)
        self.detail_canvas.delete("all")
        self.detail_canvas.update_idletasks()
        cw = max(self.calendar_w - 24, self.detail_canvas.winfo_width())

        status_badge = " (تعطیل)" if info["is_holiday"] else ""
        header_text = format_digits(f"{info['date_text']}{status_badge}", use_fa)

        draw_outlined_canvas_text(
            self.detail_canvas,
            cw - 4,
            4,
            text=header_text,
            font_spec=(font_fa, 9, "bold"),
            fill=self.config["holiday_color"] if info["is_holiday"] else self.config["accent_color"],
            outline="#000000",
            anchor="ne",
            justify="right",
        )

        lines = []
        for title, is_hol in info.get("events", []):
            prefix = "🔴 " if is_hol else "• "
            lines.append(f"{prefix}{title}")

        user_alarms = self.alarm_store.get_events_for_jalali_day(
            info["jy"], info["jm"], info["jd"], info["persian_week_idx"]
        )
        for a in user_alarms:
            t_str = f"{int(a.get('hour', 0)):02d}:{int(a.get('minute', 0)):02d}"
            lines.append(f"⏰ {t_str} - {a.get('title', '')}")

        if lines:
            occ_text = format_digits("\n".join(lines[:3]), use_fa)
            draw_outlined_canvas_text(
                self.detail_canvas,
                cw - 4,
                26,
                text=occ_text,
                font_spec=(font_fa, 8),
                fill=self.config["holiday_color"] if (info["is_holiday"] and info["has_occasion"]) else self.config["date_color"],
                outline="#000000",
                anchor="ne",
                justify="right",
                width=cw - 8,
            )

    def _change_month(self, delta: int):
        if self.config.get("locked", False):
            return
        new_jm = self.view_jm + delta
        new_jy = self.view_jy
        if new_jm > 12:
            new_jm = 1
            new_jy += 1
        elif new_jm < 1:
            new_jm = 12
            new_jy -= 1
        self.view_jy = new_jy
        self.view_jm = new_jm
        month_data = get_month_calendar(self.view_jy, self.view_jm, CUSTOM_OCCASIONS_PATH)
        if self.view_jy == self.current_jy and self.view_jm == self.current_jm:
            for d_info in month_data["days"]:
                if d_info["jd"] == self.current_jd:
                    self.selected_day_info = d_info
                    break
        else:
            self.selected_day_info = month_data["days"][0]
        self._render_calendar_month()

    def _go_to_today(self):
        if self.config.get("locked", False):
            return
        today = get_today_info(CUSTOM_OCCASIONS_PATH)
        self.view_jy = today["jy"]
        self.view_jm = today["jm"]
        self.selected_day_info = today
        self._render_calendar_month()

    def _toggle_calendar(self, event=None):
        if event is not None and self.config.get("locked", False):
            return "break"
        expanded = not self.config.get("calendar_expanded", False)
        self.config["calendar_expanded"] = expanded
        self._save_config()
        self._sync_calendar_visibility()
        return "break"

    def _sync_calendar_visibility(self):
        expanded = self.config.get("calendar_expanded", False)
        is_locked = bool(self.config.get("locked", False))
        z_mode = self.config.get("z_mode", "topmost")

        if expanded:
            today = get_today_info(CUSTOM_OCCASIONS_PATH)
            self.view_jy = today["jy"]
            self.view_jm = today["jm"]
            if not self.selected_day_info:
                self.selected_day_info = today
            self._position_calendar_window()
            self.cal_win.deiconify()
            self.cal_win.lift()
            self._render_calendar_month()
            hide_from_taskbar(self.cal_win)
            cw, ch = self._get_calendar_size()
            apply_rounded_corners(self.cal_win, cw, ch, radius=16, enabled=True)
            cal_alpha = max(0.85, float(self.config.get("opacity", 0.90)))
            if is_locked and cal_alpha >= 1.0:
                cal_alpha = 0.99
            self.cal_win.attributes("-alpha", cal_alpha)
            apply_z_order_and_clickthrough(self.cal_win, z_mode, click_through=is_locked)
            self.extend_btn.configure(text="▸ بستن")
        else:
            if self.cal_win:
                self.cal_win.withdraw()
            self.extend_btn.configure(text="📅 تقویم")
        return "break"

    def _get_calendar_size(self) -> tuple[int, int]:
        if self.cal_win and self.cal_win.winfo_exists():
            self.cal_win.update_idletasks()
            cw = max(self.calendar_w, self.cal_win.winfo_reqwidth())
            ch = max(self.calendar_h, self.cal_win.winfo_reqheight())
            return cw, ch
        return self.calendar_w, self.calendar_h

    def _position_calendar_window(self):
        if not self.cal_win or not self.widget_win:
            return
        cw, ch = self._get_calendar_size()

        # در صورتی که ویجت دسکتاپ مخفی است، تقویم بالای ساعت گوشه مانیتور محل کلیک باز شود
        hide_desktop = (
            bool(self.config.get("replace_windows_clock", False))
            and bool(self.config.get("replace_clock_hide_widget", False))
        )
        if hide_desktop or not self.widget_win.winfo_viewable():
            try:
                px = self.root.winfo_pointerx()
                py = self.root.winfo_pointery()
            except Exception:
                px, py = 0, 0
            ml, mt, mr, mb = get_monitor_work_area_at(px, py, self.root)
            cx = mr - cw - 12
            cy = mb - ch - 12
            self.cal_win.geometry(f"{cw}x{ch}+{int(cx)}+{int(cy)}")
            return

        wx = self.widget_win.winfo_x()
        wy = self.widget_win.winfo_y()
        ww, wh = self.compact_w, self.compact_h
        ml, mt, mr, mb = get_monitor_work_area_at(wx + ww // 2, wy + wh // 2, self.root)

        mode = self.config.get("calendar_position", "beside")
        if mode == "below":
            cx = wx + ww - cw
            cy = wy + wh + self.GAP
            if cy + ch > mb - 8:
                cy = wy - ch - self.GAP
        else:
            if wx - cw - self.GAP >= ml + 8:
                cx = wx - cw - self.GAP
            else:
                cx = wx + ww + self.GAP
            cy = wy
            if cy + ch > mb - 8:
                cy = max(mt + 8, mb - ch - 8)

        cx = max(ml + 8, min(cx, mr - cw - 8))
        cy = max(mt + 8, min(cy, mb - ch - 8))
        self.cal_win.geometry(f"{cw}x{ch}+{int(cx)}+{int(cy)}")

    def open_alarm_manager(self):
        if self.alarm_win and self.alarm_win.win and self.alarm_win.win.winfo_exists():
            self.alarm_win.win.deiconify()
            self.alarm_win.win.lift()
            self.alarm_win.win.focus_force()
            return

        sel = self.selected_day_info or get_today_info(CUSTOM_OCCASIONS_PATH)
        init_jalali = (sel["jy"], sel["jm"], sel["jd"])
        self.alarm_win = AlarmManagerWindow(
            root=self.root,
            store=self.alarm_store,
            font_family=self.config.get("font_family", "Vazir"),
            initial_jalali=init_jalali,
            on_change_callback=self._on_alarms_updated,
        )

    def _load_custom_occasions_dict(self) -> dict:
        if os.path.exists(CUSTOM_OCCASIONS_PATH):
            try:
                with open(CUSTOM_OCCASIONS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def _save_custom_occasions_dict(self, data: dict):
        os.makedirs(os.path.dirname(CUSTOM_OCCASIONS_PATH), exist_ok=True)
        with open(CUSTOM_OCCASIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def open_custom_occasions_manager(self):
        """پنجره مدیریت مناسبت‌های شخصی و تولد دوستان + ثبت خودکار آلارم یادآور ۱ روز قبل"""
        if self.custom_occ_win and self.custom_occ_win.winfo_exists():
            self.custom_occ_win.deiconify()
            self.custom_occ_win.lift()
            self.custom_occ_win.focus_force()
            return

        font_fa = self.config.get("font_family", "Vazir")
        sel = self.selected_day_info or get_today_info(CUSTOM_OCCASIONS_PATH)
        init_m = int(sel.get("jm", 1))
        init_d = int(sel.get("jd", 1))
        init_y = int(sel.get("jy", 1405))

        win = tk.Toplevel(self.root)
        self.custom_occ_win = win
        win.title("🎂 مدیریت مناسبت‌های شخصی و تولدها")
        win.configure(bg="#0F172A")
        win.attributes("-topmost", True)
        w, h = 470, 520
        wx = self.widget_win.winfo_x() if self.widget_win else 0
        wy = self.widget_win.winfo_y() if self.widget_win else 0
        ml, mt, mr, mb = get_monitor_work_area_at(wx + 50, wy + 50, self.root)
        sx = ml + ((mr - ml) - w) // 2
        sy = mt + ((mb - mt) - h) // 2
        win.geometry(f"{w}x{h}+{int(sx)}+{int(sy)}")
        win.resizable(False, False)

        container = tk.Frame(win, bg="#0F172A", padx=14, pady=12)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="🎂 ثبت روز تولد دوستان و مناسبت‌های شخصی در تقویم",
            font=(font_fa, 10, "bold"),
            fg="#F472B6",
            bg="#0F172A",
        ).pack(anchor="e", pady=(0, 8))

        form = tk.LabelFrame(
            container,
            text=" افزودن مناسبت جدید ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=8,
        )
        form.pack(fill="x", pady=(0, 10))

        # عنوان مناسبت
        row1 = tk.Frame(form, bg="#1E293B")
        row1.pack(fill="x", pady=3)
        tk.Label(row1, text="عنوان:", font=(font_fa, 9), fg="#CBD5E1", bg="#1E293B").pack(side="right", padx=(6, 0))
        title_entry = tk.Entry(
            row1,
            font=(font_fa, 9),
            bg="#0F172A",
            fg="#F8FAFC",
            insertbackground="#F8FAFC",
            relief="flat",
            justify="right",
        )
        title_entry.pack(side="right", fill="x", expand=True, ipady=4, padx=(0, 6))
        title_entry.focus_set()

        # نوع مناسبت
        row2 = tk.Frame(form, bg="#1E293B")
        row2.pack(fill="x", pady=4)
        kind_var = tk.StringVar(value="birthday")
        holiday_var = tk.BooleanVar(value=False)
        prev_alarm_var = tk.BooleanVar(value=True)

        def on_kind_change():
            if kind_var.get() == "birthday":
                prev_alarm_var.set(True)
                holiday_var.set(False)
            elif kind_var.get() == "holiday":
                holiday_var.set(True)
            else:
                holiday_var.set(False)

        for val, lbl_txt, fg_c in (
            ("birthday", "🎂 روز تولد", "#F472B6"),
            ("personal", "🎉 مناسبت شخصی", "#38BDF8"),
            ("holiday", "🏖 تعطیل شخصی", "#F87171"),
        ):
            tk.Radiobutton(
                row2,
                text=lbl_txt,
                value=val,
                variable=kind_var,
                command=on_kind_change,
                font=(font_fa, 8, "bold"),
                fg=fg_c,
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
            ).pack(side="right", padx=(8, 0))

        # انتخاب ماه و روز شمسی
        row3 = tk.Frame(form, bg="#1E293B")
        row3.pack(fill="x", pady=4)
        tk.Label(row3, text="تاریخ شمسی:", font=(font_fa, 9), fg="#CBD5E1", bg="#1E293B").pack(side="right", padx=(6, 0))

        month_names = [f"{m} - {PERSIAN_MONTHS[m]}" for m in range(1, 13)]
        month_var = tk.StringVar(value=month_names[max(0, min(11, init_m - 1))])
        m_menu = tk.OptionMenu(row3, month_var, *month_names)
        m_menu.configure(
            font=(font_fa, 8, "bold"),
            bg="#0F172A",
            fg="#F8FAFC",
            activebackground="#334155",
            highlightthickness=0,
            bd=0,
        )
        m_menu["menu"].configure(bg="#0F172A", fg="#F8FAFC", font=(font_fa, 8))
        m_menu.pack(side="right", padx=(6, 0))

        tk.Label(row3, text="روز:", font=(font_fa, 9), fg="#CBD5E1", bg="#1E293B").pack(side="right", padx=(8, 4))
        day_spin = tk.Spinbox(
            row3,
            from_=1,
            to=31,
            width=4,
            font=("Segoe UI", 9, "bold"),
            bg="#0F172A",
            fg="#F8FAFC",
            buttonbackground="#334155",
        )
        day_spin.delete(0, "end")
        day_spin.insert(0, str(init_d))
        day_spin.pack(side="right")

        # تیک آلارم ۱ روز قبل (تکرار سالانه)
        row4 = tk.Frame(form, bg="#1E293B")
        row4.pack(fill="x", pady=(6, 2))
        tk.Checkbutton(
            row4,
            text="⏰ ثبت خودکار آلارم یادآور ۱ روز قبل (تکرار سالانه)",
            variable=prev_alarm_var,
            font=(font_fa, 8, "bold"),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="e",
        ).pack(side="right")

        row5 = tk.Frame(form, bg="#1E293B")
        row5.pack(fill="x", pady=2)
        tk.Label(row5, text="ساعت یادآوری روز قبل:", font=(font_fa, 8), fg="#CBD5E1", bg="#1E293B").pack(side="right", padx=(6, 0))
        sp_m = tk.Spinbox(row5, from_=0, to=59, width=3, format="%02.0f", font=("Segoe UI", 9, "bold"), bg="#0F172A", fg="#F8FAFC", buttonbackground="#334155")
        sp_m.delete(0, "end")
        sp_m.insert(0, "00")
        sp_m.pack(side="right", padx=2)
        tk.Label(row5, text=":", font=("Segoe UI", 9, "bold"), fg="#F8FAFC", bg="#1E293B").pack(side="right")
        sp_h = tk.Spinbox(row5, from_=0, to=23, width=3, format="%02.0f", font=("Segoe UI", 9, "bold"), bg="#0F172A", fg="#F8FAFC", buttonbackground="#334155")
        sp_h.delete(0, "end")
        sp_h.insert(0, "09")
        sp_h.pack(side="right", padx=2)

        status_lbl = tk.Label(form, text="", font=(font_fa, 8, "bold"), fg="#10B981", bg="#1E293B")
        status_lbl.pack(anchor="e", pady=(2, 0))

        # بخش لیست مناسبت‌های ثبت‌شده
        list_frame = tk.LabelFrame(
            container,
            text=" مناسبت‌های شخصی ثبت‌شده ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=8,
            pady=6,
        )
        list_frame.pack(fill="both", expand=True)

        list_canvas = tk.Canvas(list_frame, bg="#1E293B", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=list_canvas.yview)
        items_inner = tk.Frame(list_canvas, bg="#1E293B")
        items_inner.bind("<Configure>", lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
        list_canvas.create_window((0, 0), window=items_inner, anchor="nw")
        list_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")
        list_canvas.pack(side="right", fill="both", expand=True)

        def refresh_list():
            for ch in items_inner.winfo_children():
                ch.destroy()
            data = self._load_custom_occasions_dict()
            if not data:
                tk.Label(
                    items_inner,
                    text="هنوز مناسبتی ثبت نشده است.",
                    font=(font_fa, 8),
                    fg="#64748B",
                    bg="#1E293B",
                ).pack(pady=16, padx=10)
                return

            for mmdd in sorted(data.keys()):
                items = data.get(mmdd, [])
                try:
                    m_i, d_i = map(int, mmdd.split("-"))
                    m_name = PERSIAN_MONTHS[m_i] if 1 <= m_i <= 12 else str(m_i)
                    date_lbl = f"{d_i} {m_name}"
                except Exception:
                    date_lbl = mmdd

                for idx_i, item in enumerate(items):
                    t = item.get("title", "") if isinstance(item, dict) else str(item)
                    is_h = bool(item.get("holiday", False)) if isinstance(item, dict) else False
                    row = tk.Frame(items_inner, bg="#0F172A", padx=8, pady=5)
                    row.pack(fill="x", pady=2, padx=2)

                    def make_del(k=mmdd, ix=idx_i, occ_title=t):
                        def _del():
                            d_cur = self._load_custom_occasions_dict()
                            lst = d_cur.get(k, [])
                            if 0 <= ix < len(lst):
                                lst.pop(ix)
                                if lst:
                                    d_cur[k] = lst
                                else:
                                    d_cur.pop(k, None)
                                self._save_custom_occasions_dict(d_cur)
                                # حذف آلارم یادآور سالانه مرتبط در صورت وجود
                                clean_t = occ_title.replace("🎂 ", "").strip()
                                expected_alarm = f"🎂 یادآور فردا: {clean_t}"
                                before_n = len(self.alarm_store.alarms)
                                self.alarm_store.alarms = [
                                    a for a in self.alarm_store.alarms
                                    if not (a.get("repeat_mode") == "yearly" and a.get("title") == expected_alarm)
                                ]
                                if len(self.alarm_store.alarms) != before_n:
                                    self.alarm_store.save()
                                self._on_alarms_updated()
                                refresh_list()
                        return _del

                    tk.Button(
                        row,
                        text="🗑 حذف",
                        font=(font_fa, 8),
                        bg="#7F1D1D",
                        fg="#FCA5A5",
                        relief="flat",
                        cursor="hand2",
                        command=make_del(),
                    ).pack(side="left")

                    tk.Label(
                        row,
                        text=f"📅 {date_lbl}  —  {t}",
                        font=(font_fa, 8, "bold"),
                        fg="#F87171" if is_h else "#F8FAFC",
                        bg="#0F172A",
                        anchor="e",
                    ).pack(side="right", fill="x", expand=True, padx=(8, 0))

        def on_add_occasion():
            raw_title = title_entry.get().strip()
            if not raw_title:
                status_lbl.configure(text="لطفاً عنوان مناسبت یا نام را وارد کنید.", fg="#F87171")
                return
            try:
                jm = int(month_var.get().split("-")[0].strip())
                jd = int(day_spin.get())
                max_d = get_jalali_month_days(init_y, jm)
                jd = max(1, min(jd, max_d))
            except Exception:
                status_lbl.configure(text="تاریخ واردشده معتبر نیست.", fg="#F87171")
                return

            kind = kind_var.get()
            final_title = raw_title
            if kind == "birthday" and "🎂" not in final_title:
                final_title = f"🎂 {final_title}"

            key = f"{jm:02d}-{jd:02d}"
            data = self._load_custom_occasions_dict()
            data.setdefault(key, [])
            data[key].append({"title": final_title, "holiday": bool(holiday_var.get())})
            self._save_custom_occasions_dict(data)

            alarm_msg = ""
            if prev_alarm_var.get():
                try:
                    ah = max(0, min(23, int(sp_h.get())))
                    am = max(0, min(59, int(sp_m.get())))
                except Exception:
                    ah, am = 9, 0
                if jd > 1:
                    pm, pd = jm, jd - 1
                else:
                    pm = 12 if jm == 1 else jm - 1
                    pd = get_jalali_month_days(init_y, pm)
                prev_key = f"{pm:02d}-{pd:02d}"
                clean_t = final_title.replace("🎂 ", "").strip()
                self.alarm_store.add_or_update({
                    "title": f"🎂 یادآور فردا: {clean_t}",
                    "hour": ah,
                    "minute": am,
                    "repeat_mode": "yearly",
                    "yearly_days": [prev_key],
                    "enabled": True,
                    "play_sound": True,
                })
                alarm_msg = f" + آلارم روز قبل ({pd} {PERSIAN_MONTHS[pm]} ساعت {ah:02d}:{am:02d})"

            title_entry.delete(0, "end")
            status_lbl.configure(text=f"✓ «{final_title}» ثبت شد{alarm_msg}", fg="#10B981")
            self._on_alarms_updated()
            refresh_list()

        tk.Button(
            form,
            text="✓ افزودن مناسبت به تقویم",
            font=(font_fa, 9, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            padx=12,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=on_add_occasion,
        ).pack(anchor="w", pady=(6, 0))

        refresh_list()
        hide_from_taskbar(win)
        apply_rounded_corners(win, w, h, radius=14, enabled=True)

    def _on_alarms_updated(self):
        self._refresh_display()
        if self.config.get("calendar_expanded"):
            self._render_calendar_month()

    def _on_alarm_dismissed(self, alarm: dict):
        """وقتی آلارم بدون Snooze بسته شد، اگر یک‌باره یا تاریخ‌محور بود از لیست حذف شود"""
        removed = self.alarm_store.on_alarm_dismissed(alarm)
        if removed:
            self._on_alarms_updated()
            if self.alarm_win and self.alarm_win.win and self.alarm_win.win.winfo_exists():
                self.alarm_win._refresh_list()
                self.alarm_win._render_picker_calendar()

    def _init_position(self):
        ww, wh = self.compact_w, self.compact_h

        x = self.config.get("x")
        y = self.config.get("y")
        if x is None or y is None:
            ml, mt, mr, mb = get_monitor_work_area_at(0, 0, self.root)
            x = mr - ww - 32
            y = mt + 32
            self.config["x"] = x
            self.config["y"] = y
            self._save_config()
        else:
            ml, mt, mr, mb = get_monitor_work_area_at(int(x) + ww // 2, int(y) + wh // 2, self.root)

        if self.config.get("locked"):
            snap_side = self.config.get("snap_side", "right")
            x = (mr - ww) if snap_side == "right" else ml

        x = max(ml, min(int(x), mr - ww))
        y = max(mt, min(int(y), mb - wh))
        self.widget_win.geometry(f"{ww}x{wh}+{x}+{y}")
        self._position_lock_window()

    def _apply_all_styles(self):
        if not self.widget_win:
            return

        hide_from_taskbar(self.widget_win)
        if self.lock_win:
            hide_from_taskbar(self.lock_win)

        is_locked = bool(self.config.get("locked", False))
        transparent_bg = bool(self.config.get("transparent_bg", False))
        bg_color = self.config.get("bg_color", "#141821")
        border_color = self.config.get("border_color", "#2A3244")
        bg = TRANSPARENT_KEY if transparent_bg else bg_color

        self.widget_win.configure(bg=bg)
        self.main_frame.configure(
            bg=bg,
            highlightbackground=border_color if not transparent_bg else bg,
            highlightthickness=0 if transparent_bg else 1,
        )
        self.canvas.configure(bg=bg)
        dock_bg = "#161E2E" if not transparent_bg else bg
        dock_border = "#2A364F" if not transparent_bg else bg
        if hasattr(self, "win_controls_container"):
            self.win_controls_container.configure(
                bg=dock_bg,
                highlightbackground=dock_border,
                highlightthickness=0 if transparent_bg else 1,
            )
        self.btn_container.configure(
            bg=dock_bg,
            highlightbackground=dock_border,
            highlightthickness=0 if transparent_bg else 1,
        )
        for sub_f in (getattr(self, "_dock_row1", None), getattr(self, "_dock_row2", None)):
            if sub_f is not None:
                sub_f.configure(bg=dock_bg)
        if hasattr(self, "_dock_hdiv"):
            self._dock_hdiv.configure(bg="#243047" if not transparent_bg else bg)
        for sep in getattr(self, "_toolbar_seps", []):
            sep.configure(bg=dock_bg)

        btn_bg = self._get_btn_base_bg()
        font_fa = self.config.get("font_family", "Vazir")

        for tip in self._tooltips:
            tip.font_family = font_fa

        self.extend_btn.configure(
            bg=btn_bg,
            fg=self.config.get("accent_color", "#38BDF8"),
            font=(font_fa, 8, "bold"),
        )
        self.copy_time_btn.configure(bg=btn_bg, fg="#A7F3D0", font=(font_fa, 8, "bold"))
        self.guid_btn.configure(bg=btn_bg, fg="#C4B5FD")
        if hasattr(self, "dev_ai_btn"):
            self.dev_ai_btn.configure(bg=btn_bg, fg="#38BDF8")
        self.alarm_btn.configure(bg=btn_bg, fg="#FBBF24", font=(font_fa, 8, "bold"))
        if hasattr(self, "occ_btn"):
            self.occ_btn.configure(bg=btn_bg, fg="#F472B6", font=(font_fa, 8, "bold"))
        self.settings_btn.configure(
            bg=btn_bg,
            fg=self.config.get("date_color", "#CBD5E1"),
        )
        if hasattr(self, "tz_btn"):
            self._update_tz_btn_appearance()
        if hasattr(self, "min_btn"):
            self.min_btn.configure(
                bg=btn_bg,
                fg=self.config.get("date_color", "#CBD5E1"),
            )
        if hasattr(self, "close_btn"):
            self.close_btn.configure(bg=btn_bg, fg="#FCA5A5")

        self._refresh_display()

        ww, wh = self.compact_w, self.compact_h
        cur_x = self.widget_win.winfo_x()
        cur_y = self.widget_win.winfo_y()
        ml, mt, mr, mb = get_monitor_work_area_at(cur_x + ww // 2, cur_y + wh // 2, self.root)
        if is_locked:
            snap_side = self.config.get("snap_side", "right")
            pos_x = (mr - ww) if snap_side == "right" else ml
            pos_y = max(mt, min(cur_y, mb - wh))
        else:
            pos_x = max(ml, min(cur_x, mr - ww))
            pos_y = max(mt, min(cur_y, mb - wh))
        self.widget_win.geometry(f"{ww}x{wh}+{int(pos_x)}+{int(pos_y)}")
        self._position_lock_window()

        alpha_val = float(self.config.get("opacity", 0.90))
        if is_locked and alpha_val >= 1.0:
            alpha_val = 0.99

        if transparent_bg:
            apply_rounded_corners(self.widget_win, ww, wh, enabled=False)
            self.widget_win.attributes("-transparentcolor", TRANSPARENT_KEY)
            self.widget_win.attributes("-alpha", alpha_val)
        else:
            self.widget_win.attributes("-transparentcolor", "")
            self.widget_win.attributes("-alpha", alpha_val)
            apply_rounded_corners(self.widget_win, ww, wh, radius=16, enabled=True)

        z_mode = self.config.get("z_mode", "topmost")
        if self.lock_win:
            lock_bg = "#1E2638" if not transparent_bg else "#141821"
            lock_border = "#F59E0B" if is_locked else border_color
            self.lock_win.configure(bg=lock_bg)
            self.lock_frame.configure(bg=lock_bg, highlightbackground=lock_border, highlightthickness=1)
            self.lock_btn_label.configure(
                text="🔒" if is_locked else "🔓",
                fg="#FBBF24" if is_locked else self.config.get("accent_color", "#38BDF8"),
                bg=lock_bg,
            )
            apply_rounded_corners(self.lock_win, self.LOCK_BTN_SIZE, self.LOCK_BTN_SIZE, radius=6, enabled=True)
            self.lock_win.attributes("-alpha", max(0.85, alpha_val))
            apply_z_order_and_clickthrough(self.lock_win, z_mode, click_through=False)

        if self.cal_win:
            self.cal_win.configure(bg=bg_color)
            self.cal_frame.configure(bg=bg_color, highlightbackground=border_color)
            self.cal_header.configure(bg=bg_color)
            self.week_header.configure(bg=bg_color)
            self.days_grid_frame.configure(bg=bg_color)
            self.cal_sep.configure(bg=border_color)
            self.cal_bottom_bar.configure(bg=bg_color)
            self.cal_copyright_lbl.configure(bg=bg_color)
            self.add_event_btn.configure(font=(font_fa, 8, "bold"))
            self.today_btn.configure(font=(font_fa, 8, "bold"))

        apply_z_order_and_clickthrough(
            self.widget_win,
            z_mode,
            click_through=is_locked,
        )
        if self.lock_win:
            apply_z_order_and_clickthrough(self.lock_win, z_mode, click_through=False)

        self._sync_calendar_visibility()

    def _on_drag_start(self, event):
        if self.config.get("locked", False):
            return
        self._close_dev_popup_window()
        self._is_dragging = True
        self._drag_start_x = event.x_root - self.widget_win.winfo_x()
        self._drag_start_y = event.y_root - self.widget_win.winfo_y()

    def _on_drag_motion(self, event):
        if not self._is_dragging or self.config.get("locked", False):
            return
        new_x = int(event.x_root - self._drag_start_x)
        new_y = int(event.y_root - self._drag_start_y)
        self.widget_win.geometry(f"{self.compact_w}x{self.compact_h}+{new_x}+{new_y}")
        self._position_lock_window(new_x, new_y)
        if self.config.get("calendar_expanded", False):
            self._position_calendar_window()

    def _on_drag_end(self, event):
        if not self._is_dragging:
            return
        self._is_dragging = False
        self.widget_win.update_idletasks()
        wx = self.widget_win.winfo_x()
        wy = self.widget_win.winfo_y()
        self.config["x"] = wx
        self.config["y"] = wy
        self._unlocked_x = wx
        self._unlocked_y = wy
        self._save_config()
        self._position_lock_window(wx, wy)
        z_mode = self.config.get("z_mode", "topmost")
        is_locked = bool(self.config.get("locked", False))
        apply_z_order_and_clickthrough(self.widget_win, z_mode, click_through=is_locked)
        if self.lock_win:
            apply_z_order_and_clickthrough(self.lock_win, z_mode, click_through=False)

    def _build_context_menu(self):
        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#1E293B",
            fg="#F8FAFC",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            font=("Tahoma", 9),
        )

    def _populate_context_menu(self):
        self.menu.delete(0, "end")

        locked_label = (
            "🔓 باز کردن قفل ویجت (فعال‌سازی کلیک و جابه‌جایی)"
            if self.config.get("locked")
            else "🔒 قفل و فیکس کردن ویجت (کوچک‌ترین حالت و چسبیدن به لبه صفحه)"
        )
        self.menu.add_command(label=locked_label, command=self._toggle_lock)
        self.menu.add_separator()

        if getattr(self, "_is_minimized", False):
            self.menu.add_command(
                label="🗖 نمایش مجدد ویجت روی صفحه (Restore)",
                command=self.restore_widget,
            )
        else:
            self.menu.add_command(
                label="🗕 مینیمایز / بستن به Hidden Icons (بدون آیکون در تسک‌بار)",
                command=self.minimize_widget,
            )
        self.menu.add_separator()

        is_utc_primary = self.config.get("primary_timezone", "tehran") == "utc"
        tz_label = (
            "🕒 ساعت اصلی: UTC (تبدیل به تهران)"
            if is_utc_primary
            else "🕒 ساعت اصلی: تهران (تبدیل به UTC)"
        )
        self.menu.add_command(label=tz_label, command=self._toggle_primary_timezone)
        utc_row_label = (
            "✓ 🌐 نمایش ردیف زمان UTC/تهران در ویجت (فعال)"
            if self.config.get("show_utc")
            else "🌐 نمایش ردیف زمان UTC در ویجت"
        )
        self.menu.add_command(label=utc_row_label, command=self._toggle_show_utc)
        sec_label = (
            "✓ ⏱ نمایش ثانیه در ساعت (همه‌جا - فعال)"
            if self.config.get("show_seconds")
            else "⏱ نمایش ثانیه در ساعت (همه‌جا)"
        )
        self.menu.add_command(label=sec_label, command=self._toggle_show_seconds)
        self.menu.add_separator()

        self.menu.add_command(
            label="🎲 رندر و کپی فوری GUID جدید (UUID v4)",
            command=lambda: self._copy_to_clipboard(str(uuid.uuid4()), "✓ GUID کپی شد!"),
        )
        self.menu.add_command(
            label="📋 باز کردن پنل کپی زمان (۱۰ فرمت API) و GUID...",
            command=self._toggle_dev_popup_window,
        )

        self._populate_dev_copy_menu()
        self.menu.add_cascade(
            label="🕒 لیست سریع فرمت‌های زمان API و GUID",
            menu=self.copy_menu,
        )
        self.menu.add_separator()

        self.menu.add_command(
            label="⏰ مدیریت رویدادها و آلارم‌ها...",
            command=self.open_alarm_manager,
        )
        self.menu.add_command(
            label="🎂 مدیریت مناسبت‌های شخصی و تولدها...",
            command=self.open_custom_occasions_manager,
        )
        self.menu.add_command(
            label="🌐 وضعیت IP و قفل شهر/لوکیشن...",
            command=self.open_ip_monitor_window,
        )
        self.menu.add_command(
            label="⚡ ابزارهای هوشمند (Cron / JWT / AI / پومودورو)...",
            command=self.open_dev_ai_hub,
        )

        self.menu.add_command(
            label="⚙️ تنظیمات ظاهری، رنگ، سایز و فونت...",
            command=self.open_settings_window,
        )

        cal_text = "▾ بستن تقویم ماهانه" if self.config.get("calendar_expanded") else "📅 نمایش تقویم ماهانه (Extend)"
        self.menu.add_command(label=cal_text, command=lambda: self._toggle_calendar(None))

        z_menu = tk.Menu(
            self.menu,
            tearoff=0,
            bg="#1E293B",
            fg="#F8FAFC",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            font=("Tahoma", 9),
        )
        cur_z = self.config.get("z_mode", "topmost")
        for mode_key, mode_title in [
            ("topmost", "همیشه روی تمام برنامه‌ها (Z-Index بالا - پیشنهادی)"),
            ("desktop", "چسبیده به دسکتاپ (پشت پنجره‌های باز)"),
        ]:
            prefix = "✓ " if cur_z == mode_key else ""
            z_menu.add_command(
                label=f"{prefix}{mode_title}",
                command=lambda m=mode_key: self._set_z_mode(m),
            )
        self.menu.add_cascade(label="📌 لایه قرارگیری (Z-Index)", menu=z_menu)

        bg_label = (
            "✓ 🖼 حالت: بدون پس‌زمینه (تغییر به کارت با پس‌زمینه)"
            if self.config.get("transparent_bg")
            else "🖼 حالت: با پس‌زمینه (تغییر به بدون پس‌زمینه)"
        )
        self.menu.add_command(label=bg_label, command=self._toggle_transparent_bg)

        digits_label = (
            "🔢 نمایش اعداد: فارسی (تغییر به انگلیسی)"
            if self.config.get("persian_digits")
            else "🔢 نمایش اعداد: انگلیسی (تغییر به فارسی)"
        )
        self.menu.add_command(label=digits_label, command=self._toggle_digits)

        self.menu.add_separator()

        startup_on = is_startup_enabled()
        os_name_fa = "ویندوز" if sys.platform == "win32" else "لینوکس"
        startup_label = f"✓ 🚀 اجرا با شروع {os_name_fa} (فعال)" if startup_on else f"🚀 اجرا خودکار با شروع {os_name_fa} (Startup)"
        self.menu.add_command(label=startup_label, command=self._toggle_startup)

        # جایگزینی کامل ساعت ویندوز در تسک‌بار
        replace_clk_label = (
            "✓ ⭐ جایگزینی کامل ساعت و تاریخ ویندوز در تسک‌بار (فعال)"
            if self.config.get("replace_windows_clock")
            else "⭐ جایگزینی کامل ساعت و تاریخ ویندوز در تسک‌بار"
        )
        self.menu.add_command(label=replace_clk_label, command=lambda: self._toggle_taskbar_setting("replace_windows_clock"))

        if self.config.get("replace_windows_clock"):
            hide_desk_label = (
                "✓ 👁️ مخفی کردن ویجت دسکتاپ (فقط ساعت تسک‌بار)"
                if self.config.get("replace_clock_hide_widget")
                else "👁️ مخفی کردن ویجت دسکتاپ (فقط ساعت تسک‌بار)"
            )
            self.menu.add_command(label=hide_desk_label, command=lambda: self._toggle_taskbar_setting("replace_clock_hide_widget"))

        tb_clock_label = (
            "✓ 🕒 نمایش ساعت و تاریخ شناور روی تسک‌بار (فعال)"
            if self.config.get("taskbar_clock")
            else "🕒 نمایش ساعت و تاریخ شناور روی تسک‌بار"
        )
        self.menu.add_command(label=tb_clock_label, command=lambda: self._toggle_taskbar_setting("taskbar_clock"))
        tb_btn_label = (
            "✓ 📌 نمایش آیکون برنامه در تسک‌بار (فعال)"
            if self.config.get("taskbar_button")
            else "📌 نمایش آیکون برنامه در تسک‌بار"
        )
        self.menu.add_command(label=tb_btn_label, command=lambda: self._toggle_taskbar_setting("taskbar_button"))

        self.menu.add_command(label="🔄 بازنشانی مکان به گوشه مانیتور", command=self._reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="® Shayan Bamyar", state="disabled")
        self.menu.add_command(label="❌ خروج کامل از ویجت", command=self.quit_app)

    def _show_context_menu(self, event):
        if self.config.get("locked", False):
            return
        self._populate_context_menu()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _set_z_mode(self, mode: str):
        self.config["z_mode"] = mode
        self._save_config()
        self._apply_all_styles()

    def _toggle_lock(self):
        self._close_dev_popup_window()
        going_to_lock = not self.config.get("locked", False)
        self.config["locked"] = going_to_lock
        wx = self.widget_win.winfo_x() if self.widget_win else int(self.config.get("x") or 0)
        wy = self.widget_win.winfo_y() if self.widget_win else int(self.config.get("y") or 0)
        ml, _mt, mr, _mb = get_monitor_work_area_at(wx + self.compact_w // 2, wy + self.compact_h // 2, self.root)
        if going_to_lock:
            # ذخیره مکان آزاد قبل از قفل و تعیین جهت چسبیدن به لبه مانیتور فعلی (چپ یا راست)
            if self.widget_win:
                self._unlocked_x = wx
                self._unlocked_y = wy
                center_x = wx + (self.compact_w / 2)
                self.config["snap_side"] = "right" if center_x >= ((ml + mr) / 2) else "left"
            if self.config.get("calendar_expanded", False):
                self.config["calendar_expanded"] = False
        else:
            # هنگام باز کردن قفل، مکان در همان مانیتور فعلی بماند و از صفحه بیرون نزند
            if self.config.get("snap_side") == "right":
                self.config["x"] = max(ml + 10, mr - self.BASE_MIN_W - 20)
            elif getattr(self, "_unlocked_x", None) is not None:
                self.config["x"] = max(ml + 10, min(int(self._unlocked_x), mr - self.BASE_MIN_W - 10))
        self._save_config()
        self._apply_all_styles()
        if hasattr(self, "_settings_lock_var") and self._settings_lock_var is not None:
            try:
                self._settings_lock_var.set(bool(self.config["locked"]))
            except Exception:
                pass

    def _toggle_transparent_bg(self):
        self.config["transparent_bg"] = not self.config.get("transparent_bg", False)
        self._save_config()
        self._apply_all_styles()

    def _toggle_digits(self):
        self.config["persian_digits"] = not self.config.get("persian_digits", False)
        self._save_config()
        self._apply_all_styles()

    def _toggle_startup(self):
        cur = is_startup_enabled()
        set_startup_enabled(not cur, os.path.abspath(sys.argv[0]))

    def _reset_position(self):
        self.config["x"] = None
        self.config["y"] = None
        self._init_position()
        if self.config.get("calendar_expanded"):
            self._position_calendar_window()

    def open_settings_window(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.deiconify()
            self.settings_win.lift()
            self.settings_win.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.settings_win = win
        win.title("تنظیمات ویجت ساعت و تقویم شمسی")
        win.configure(bg="#0F172A")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        ico_path = get_resource_path(os.path.join("assets", "icons", "app_icon.ico"))
        if os.path.exists(ico_path):
            try:
                win.iconbitmap(ico_path)
            except Exception:
                pass

        w_width, w_height = 500, 800
        sx = (win.winfo_screenwidth() - w_width) // 2
        sy = (win.winfo_screenheight() - w_height) // 2
        win.geometry(f"{w_width}x{w_height}+{sx}+{sy}")

        font_fa = self.config.get("font_family", "Vazir")
        container = tk.Frame(win, bg="#0F172A", padx=18, pady=14)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="⚙️ تنظیمات ظاهری و رفتاری ویجت",
            font=(font_fa, 12, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 8))

        sec1 = tk.LabelFrame(
            container,
            text=" ۱. لایه نمایش (Z-Index) و قفل روی صفحه ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec1.pack(fill="x", pady=(0, 8))

        z_var = tk.StringVar(value=self.config.get("z_mode", "topmost"))

        def on_z_change():
            self.config["z_mode"] = z_var.get()
            self._save_config()
            self._apply_all_styles()

        for val, txt in [
            ("topmost", "همیشه روی تمام برنامه‌ها (با باز شدن برنامه‌ها، ویجت روی آن‌ها می‌ماند)"),
            ("desktop", "چسبیده به والپیپر دسکتاپ (پشت پنجره‌های باز)"),
        ]:
            tk.Radiobutton(
                sec1,
                text=txt,
                variable=z_var,
                value=val,
                command=on_z_change,
                font=(font_fa, 8),
                fg="#F8FAFC",
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
                activeforeground="#38BDF8",
                anchor="w",
            ).pack(fill="x", pady=1)

        self._settings_lock_var = tk.BooleanVar(value=bool(self.config.get("locked", False)))

        def on_lock_change():
            new_locked = self._settings_lock_var.get()
            self.config["locked"] = new_locked
            wx = self.widget_win.winfo_x() if self.widget_win else int(self.config.get("x") or 0)
            wy = self.widget_win.winfo_y() if self.widget_win else int(self.config.get("y") or 0)
            ml, _mt, mr, _mb = get_monitor_work_area_at(wx + self.compact_w // 2, wy + self.compact_h // 2, self.root)
            if new_locked:
                if self.widget_win:
                    self._unlocked_x = wx
                    self._unlocked_y = wy
                    center_x = wx + (self.compact_w / 2)
                    self.config["snap_side"] = "right" if center_x >= ((ml + mr) / 2) else "left"
                if self.config.get("calendar_expanded", False):
                    self.config["calendar_expanded"] = False
            else:
                if self.config.get("snap_side") == "right":
                    self.config["x"] = max(ml + 10, mr - self.BASE_MIN_W - 20)
                elif getattr(self, "_unlocked_x", None) is not None:
                    self.config["x"] = max(ml + 10, min(int(self._unlocked_x), mr - self.BASE_MIN_W - 10))
            self._save_config()
            self._apply_all_styles()

        tk.Checkbutton(
            sec1,
            text="قفل و فیکس کردن ویجت (🔒 عبوردهی کلیک به برنامه زیرین؛ فقط دکمه قفل قابل کلیک است)",
            variable=self._settings_lock_var,
            command=on_lock_change,
            font=(font_fa, 8, "bold"),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(anchor="w", pady=(4, 0))

        startup_var = tk.BooleanVar(value=is_startup_enabled())
        os_name_fa = "ویندوز" if sys.platform == "win32" else "لینوکس"

        def on_startup_change():
            want = bool(startup_var.get())
            script_target = os.path.abspath(sys.argv[0]) if sys.argv else os.path.abspath(__file__)
            ok = set_startup_enabled(want, script_target)
            if not ok:
                startup_var.set(is_startup_enabled())

        tk.Checkbutton(
            sec1,
            text=f"🚀 اجرا خودکار ویجت هم‌زمان با بالا آمدن {os_name_fa} (Startup)",
            variable=startup_var,
            command=on_startup_change,
            font=(font_fa, 8, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(anchor="w", pady=(2, 0))

        sec2 = tk.LabelFrame(
            container,
            text=" ۲. پس‌زمینه و میزان شفافیت ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec2.pack(fill="x", pady=(0, 8))

        trans_var = tk.BooleanVar(value=bool(self.config.get("transparent_bg", False)))

        def on_trans_change():
            self.config["transparent_bg"] = trans_var.get()
            self._save_config()
            self._apply_all_styles()

        tk.Checkbutton(
            sec2,
            text="حالت بدون پس‌زمینه (نمایش فقط متن با خط دور مشکی روی صفحه)",
            variable=trans_var,
            command=on_trans_change,
            font=(font_fa, 8, "bold"),
            fg="#F8FAFC",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(anchor="w")

        op_row = tk.Frame(sec2, bg="#1E293B")
        op_row.pack(fill="x", pady=(4, 0))
        tk.Label(
            op_row,
            text="شفافیت کل ویجت (%):",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right")

        op_scale = tk.Scale(
            op_row,
            from_=25,
            to=100,
            orient="horizontal",
            bg="#1E293B",
            fg="#F8FAFC",
            highlightthickness=0,
            troughcolor="#0F172A",
            length=220,
            command=lambda v: self._on_opacity_slider(int(v)),
        )
        op_scale.set(int(float(self.config.get("opacity", 0.90)) * 100))
        op_scale.pack(side="left")

        sec3 = tk.LabelFrame(
            container,
            text=" ۳. انتخاب رنگ نوشته‌ها و پس‌زمینه ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec3.pack(fill="x", pady=(0, 8))

        color_items = [
            ("clock_color", "رنگ ساعت:"),
            ("date_color", "رنگ تاریخ شمسی:"),
            ("occasion_color", "رنگ مناسبت‌ها:"),
            ("holiday_color", "رنگ روزهای تعطیل:"),
            ("bg_color", "رنگ کارت پس‌زمینه:"),
            ("accent_color", "رنگ دکمه‌ها و تاکید:"),
        ]

        self._color_previews: dict[str, tk.Button] = {}
        grid_colors = tk.Frame(sec3, bg="#1E293B")
        grid_colors.pack(fill="x")

        for idx, (cfg_key, label_txt) in enumerate(color_items):
            r = idx // 2
            c = (idx % 2) * 2
            tk.Label(
                grid_colors,
                text=label_txt,
                font=(font_fa, 8),
                fg="#CBD5E1",
                bg="#1E293B",
                anchor="e",
            ).grid(row=r, column=c + 1, sticky="e", padx=(6, 4), pady=3)

            btn = tk.Button(
                grid_colors,
                text="انتخاب رنگ",
                font=(font_fa, 8),
                bg=self.config.get(cfg_key, "#FFFFFF"),
                fg="#000000" if cfg_key != "bg_color" else "#FFFFFF",
                width=10,
                relief="flat",
                cursor="hand2",
                command=lambda k=cfg_key: self._pick_color(k),
            )
            btn.grid(row=r, column=c, sticky="w", padx=4, pady=3)
            self._color_previews[cfg_key] = btn

        for ci in range(4):
            grid_colors.grid_columnconfigure(ci, weight=1)

        sec4 = tk.LabelFrame(
            container,
            text=" ۴. اندازه ویجت و تنظیمات فونت (پیش‌فرض: Vazir) ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec4.pack(fill="x", pady=(0, 8))

        scale_row = tk.Frame(sec4, bg="#1E293B")
        scale_row.pack(fill="x", pady=2)
        tk.Label(
            scale_row,
            text="اندازه کلی ویجت (%):",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right")

        widget_scale_slider = tk.Scale(
            scale_row,
            from_=70,
            to=170,
            orient="horizontal",
            bg="#1E293B",
            fg="#F8FAFC",
            highlightthickness=0,
            troughcolor="#0F172A",
            length=220,
            command=lambda v: self._on_scale_slider(int(v)),
        )
        widget_scale_slider.set(int(self.config.get("widget_scale", 100)))
        widget_scale_slider.pack(side="left")

        bundled_and_std = [
            "Vazir",
            "B Yekan+",
            "A Iranian Sans",
            "Tahoma",
            "Segoe UI",
            "Calibri",
            "Arial",
            "Consolas",
        ]
        try:
            sys_fonts = set(tkfont.families())
            for pf in ["Vazirmatn", "IRANSans", "IRANSansWeb", "B Nazanin", "B Yekan", "Samim", "Shabnam"]:
                if pf in sys_fonts and pf not in bundled_and_std:
                    bundled_and_std.append(pf)
        except Exception:
            pass

        font_row = tk.Frame(sec4, bg="#1E293B")
        font_row.pack(fill="x", pady=3)
        tk.Label(
            font_row,
            text="فونت تاریخ و متون:",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right")

        font_cb = ttk.Combobox(font_row, values=bundled_and_std, state="readonly", width=20)
        font_cb.set(self.config.get("font_family", "Vazir"))
        font_cb.pack(side="left")

        clock_font_row = tk.Frame(sec4, bg="#1E293B")
        clock_font_row.pack(fill="x", pady=3)
        tk.Label(
            clock_font_row,
            text="فونت اعداد ساعت:",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right")

        clock_font_cb = ttk.Combobox(
            clock_font_row,
            values=["Vazir", "B Yekan+", "A Iranian Sans", "Segoe UI Semibold", "Tahoma", "Consolas"],
            state="readonly",
            width=20,
        )
        clock_font_cb.set(self.config.get("clock_font_family", "Vazir"))
        clock_font_cb.pack(side="left")

        def on_font_selected(event=None):
            self.config["font_family"] = font_cb.get()
            self.config["clock_font_family"] = clock_font_cb.get()
            self._save_config()
            self._apply_all_styles()

        font_cb.bind("<<ComboboxSelected>>", on_font_selected)
        clock_font_cb.bind("<<ComboboxSelected>>", on_font_selected)

        sizes_row = tk.Frame(sec4, bg="#1E293B")
        sizes_row.pack(fill="x", pady=(6, 2))

        def make_size_spin(parent, label_text, cfg_key, min_v, max_v):
            frame = tk.Frame(parent, bg="#1E293B")
            frame.pack(side="right", expand=True)
            tk.Label(
                frame,
                text=label_text,
                font=(font_fa, 8),
                fg="#CBD5E1",
                bg="#1E293B",
            ).pack(side="right", padx=(2, 4))
            sp = tk.Spinbox(
                frame,
                from_=min_v,
                to=max_v,
                width=4,
                font=("Segoe UI", 9),
                bg="#0F172A",
                fg="#F8FAFC",
                buttonbackground="#334155",
            )
            sp.delete(0, "end")
            sp.insert(0, str(self.config.get(cfg_key, 10)))

            def on_spin_change(*args):
                try:
                    val = int(sp.get())
                    if min_v <= val <= max_v:
                        self.config[cfg_key] = val
                        self._save_config()
                        self._apply_all_styles()
                except ValueError:
                    pass

            sp.configure(command=on_spin_change)
            sp.bind("<Return>", on_spin_change)
            sp.bind("<FocusOut>", on_spin_change)
            sp.pack(side="left")

        make_size_spin(sizes_row, "ساعت:", "clock_font_size", 12, 52)
        make_size_spin(sizes_row, "تاریخ:", "date_font_size", 6, 28)
        make_size_spin(sizes_row, "مناسبت:", "occasion_font_size", 6, 22)

        sec5 = tk.LabelFrame(
            container,
            text=" ۵. نمایش و جایگزینی در تسک‌بار ویندوز ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec5.pack(fill="x", pady=(0, 8))

        self._settings_replace_clock_var = tk.BooleanVar(value=bool(self.config.get("replace_windows_clock", False)))
        self._settings_hide_widget_var = tk.BooleanVar(value=bool(self.config.get("replace_clock_hide_widget", False)))
        self._settings_tb_clock_var = tk.BooleanVar(value=bool(self.config.get("taskbar_clock", False)))
        self._settings_tb_btn_var = tk.BooleanVar(value=bool(self.config.get("taskbar_button", False)))
        tb_sec_var = tk.BooleanVar(value=bool(self.config.get("taskbar_clock_seconds", False)))

        def on_tb_change():
            self.config["replace_windows_clock"] = bool(self._settings_replace_clock_var.get())
            self.config["replace_clock_hide_widget"] = bool(self._settings_hide_widget_var.get())
            self.config["taskbar_clock"] = bool(self._settings_tb_clock_var.get())
            self.config["taskbar_button"] = bool(self._settings_tb_btn_var.get())
            self.config["taskbar_clock_seconds"] = bool(tb_sec_var.get())
            self._save_config()
            self.sync_taskbar_features()

        def on_reset_replacer_pos():
            self.config["replace_clock_offset"] = 8
            self.config["replace_clock_width"] = 82
            self._save_config()
            try:
                sp_rw.delete(0, "end")
                sp_rw.insert(0, "118")
            except Exception:
                pass
            if self.clock_replacer:
                self.clock_replacer.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))

        def on_tb_reset_pos():
            self.config["taskbar_clock_offset"] = None
            self._save_config()
            if self.taskbar_clock:
                self.taskbar_clock.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))

        def on_pick_replacer_bg():
            cur_c = self.config.get("replace_clock_bg", "auto")
            if cur_c == "auto":
                cur_c = "#1C1C1C"
            c = colorchooser.askcolor(initialcolor=cur_c, title="انتخاب رنگ پس‌زمینه ساعت تسک‌بار", parent=win)
            if c and c[1]:
                self.config["replace_clock_bg"] = c[1]
                self._save_config()
                if self.clock_replacer:
                    self.clock_replacer.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))

        def on_auto_replacer_bg():
            self.config["replace_clock_bg"] = "auto"
            self._save_config()
            if self.clock_replacer:
                self.clock_replacer._last_color_probe_ts = 0.0
                self.clock_replacer.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))

        win11_hide_var = tk.BooleanVar(value=get_windows11_tray_clock_hidden())

        def on_toggle_win11_clock():
            want_hide = bool(win11_hide_var.get())
            set_windows11_tray_clock_hidden(want_hide)
            try:
                os.startfile("ms-settings:dateandtime")
            except Exception:
                pass

        # الف) جایگزینی کامل ساعت ویندوز
        tk.Checkbutton(
            sec5,
            text="⭐ جایگزینی کامل ساعت و تاریخ ویندوز در تسک‌بار (پوشاندن ساعت انگلیسی با ساعت و تاریخ شمسی)",
            variable=self._settings_replace_clock_var,
            command=on_tb_change,
            font=(font_fa, 8, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="w",
        ).pack(fill="x", pady=2)

        tk.Checkbutton(
            sec5,
            text="   👁️ مخفی کردن ویجت دسکتاپ هنگام فعال بودن جایگزینی (نمایش اختصاصی در تسک‌بار)",
            variable=self._settings_hide_widget_var,
            command=on_tb_change,
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="w",
        ).pack(fill="x", pady=1)

        tk.Checkbutton(
            sec5,
            text="   🗑 حذف کامل ساعت و تاریخ انگلیسی از تسک‌بار ویندوز ۱۱ (تنظیم رسمی ویندوز)",
            variable=win11_hide_var,
            command=on_toggle_win11_clock,
            font=(font_fa, 8),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="w",
        ).pack(fill="x", pady=1)

        # ب) گزینه‌های دیگر تسک‌بار
        for var, txt in (
            (self._settings_tb_clock_var, "🕒 نمایش ساعت و تاریخ شمسی شناور روی تسک‌بار (کنار ساعت ویندوز)"),
            (tb_sec_var, "⏱ نمایش ثانیه در ساعت تسک‌بار"),
            (self._settings_tb_btn_var, "📌 نمایش دکمه/آیکون برنامه در نوار وظیفه (تسک‌بار)"),
        ):
            tk.Checkbutton(
                sec5,
                text=txt,
                variable=var,
                command=on_tb_change,
                font=(font_fa, 8),
                fg="#F8FAFC",
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
                anchor="w",
            ).pack(fill="x", pady=1)

        btn_row = tk.Frame(sec5, bg="#1E293B")
        btn_row.pack(fill="x", pady=(4, 0))

        tk.Label(
            btn_row,
            text="عرض:",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="left", padx=(0, 3))

        sp_rw = tk.Spinbox(
            btn_row,
            from_=80,
            to=200,
            width=4,
            font=("Segoe UI", 8, "bold"),
            bg="#0F172A",
            fg="#F8FAFC",
            buttonbackground="#334155",
        )
        sp_rw.delete(0, "end")
        sp_rw.insert(0, str(self.config.get("replace_clock_width", 82)))

        def on_rw_change(*args):
            try:
                val = int(sp_rw.get())
                if 80 <= val <= 200:
                    self.config["replace_clock_width"] = val
                    self._save_config()
                    if self.clock_replacer:
                        self.clock_replacer.refresh(get_today_info(CUSTOM_OCCASIONS_PATH))
            except ValueError:
                pass

        sp_rw.configure(command=on_rw_change)
        sp_rw.bind("<Return>", on_rw_change)
        sp_rw.bind("<FocusOut>", on_rw_change)
        sp_rw.pack(side="left", padx=(0, 6))

        tk.Button(
            btn_row,
            text="🔄 مکان پیش‌فرض",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            relief="flat",
            cursor="hand2",
            command=on_reset_replacer_pos,
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            btn_row,
            text="🎨 رنگ خودکار",
            font=(font_fa, 8),
            bg="#334155",
            fg="#38BDF8",
            relief="flat",
            cursor="hand2",
            command=on_auto_replacer_bg,
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            btn_row,
            text="🎨 رنگ دلخواه",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            relief="flat",
            cursor="hand2",
            command=on_pick_replacer_bg,
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            btn_row,
            text="بازنشانی ساعت شناور",
            font=(font_fa, 8),
            bg="#334155",
            fg="#CBD5E1",
            relief="flat",
            cursor="hand2",
            command=on_tb_reset_pos,
        ).pack(side="left")

        # بخش ۶: تنظیمات تایم‌زون اصلی (تهران / UTC) و نمایش UTC برای برنامه‌نویسان
        sec6 = tk.LabelFrame(
            container,
            text=" ۶. تایم‌زون اصلی و نمایش UTC (ویژه برنامه‌نویسان و سرور) ",
            font=(font_fa, 9, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            bd=1,
            padx=10,
            pady=6,
        )
        sec6.pack(fill="x", pady=(0, 8))

        self._settings_primary_tz_var = tk.StringVar(
            value=self.config.get("primary_timezone", "tehran")
        )
        self._settings_show_utc_var = tk.BooleanVar(
            value=bool(self.config.get("show_utc", False))
        )
        self._settings_show_seconds_var = tk.BooleanVar(
            value=bool(self.config.get("show_seconds", False))
        )

        def on_tz_settings_change():
            self.config["primary_timezone"] = self._settings_primary_tz_var.get()
            self.config["show_utc"] = bool(self._settings_show_utc_var.get())
            sec_on = bool(self._settings_show_seconds_var.get())
            self.config["show_seconds"] = sec_on
            self.config["taskbar_clock_seconds"] = sec_on
            self._save_config()
            self._update_tz_btn_appearance()
            self._refresh_display()

        tz_radio_row = tk.Frame(sec6, bg="#1E293B")
        tz_radio_row.pack(fill="x", pady=(0, 3))
        for tz_val, tz_txt in (
            ("tehran", "🇮🇷 ساعت اصلی: تهران (شمسی)"),
            ("utc", "🌐 ساعت اصلی: UTC (تایم سرور، بدون +03:30)"),
        ):
            tk.Radiobutton(
                tz_radio_row,
                text=tz_txt,
                variable=self._settings_primary_tz_var,
                value=tz_val,
                command=on_tz_settings_change,
                font=(font_fa, 8, "bold"),
                fg="#F8FAFC",
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
                activeforeground="#38BDF8",
            ).pack(side="left", padx=(0, 14))

        tk.Checkbutton(
            sec6,
            text="🕒 نمایش ردیف ساعت و تاریخ UTC (یا ساعت تهران در حالت UTC) داخل ویجت",
            variable=self._settings_show_utc_var,
            command=on_tz_settings_change,
            font=(font_fa, 8),
            fg="#A7F3D0",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        tk.Checkbutton(
            sec6,
            text="⏱ نمایش ثانیه در ساعت (همه‌جا: ویجت، UTC و ساعت تسک‌بار)",
            variable=self._settings_show_seconds_var,
            command=on_tz_settings_change,
            font=(font_fa, 8, "bold"),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        bottom_bar = tk.Frame(container, bg="#0F172A")
        bottom_bar.pack(fill="x", pady=(8, 0))

        tk.Button(
            bottom_bar,
            text="بستن و ذخیره",
            font=(font_fa, 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            padx=16,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=win.destroy,
        ).pack(side="left")

        tk.Label(
            bottom_bar,
            text="® Shayan Bamyar",
            font=("Segoe UI", 8, "bold"),
            fg="#64748B",
            bg="#0F172A",
        ).pack(side="left", padx=14)

        tk.Button(
            bottom_bar,
            text="بازنشانی پیش‌فرض",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=lambda: self._reset_all_defaults(win),
        ).pack(side="right")

    def _on_opacity_slider(self, val: int):
        self.config["opacity"] = round(val / 100.0, 2)
        self._save_config()
        self._apply_all_styles()

    def _on_scale_slider(self, val: int):
        self.config["widget_scale"] = int(val)
        self._save_config()
        self._apply_all_styles()

    def _pick_color(self, cfg_key: str):
        initial = self.config.get(cfg_key, "#FFFFFF")
        color_code = colorchooser.askcolor(
            color=initial,
            title="انتخاب رنگ دلخواه",
            parent=self.settings_win if self.settings_win else self.root,
        )
        if color_code and color_code[1]:
            hex_c = color_code[1]
            self.config[cfg_key] = hex_c
            self._save_config()
            if cfg_key in self._color_previews and self._color_previews[cfg_key].winfo_exists():
                self._color_previews[cfg_key].configure(bg=hex_c)
            self._apply_all_styles()

    def _reset_all_defaults(self, settings_win):
        x, y = self.config.get("x"), self.config.get("y")
        self.config = DEFAULT_CONFIG.copy()
        self.config["x"] = x
        self.config["y"] = y
        self._save_config()
        self._apply_all_styles()
        self.sync_taskbar_features()
        if settings_win and settings_win.winfo_exists():
            settings_win.destroy()
            self.open_settings_window()

    def _on_tray_left_click(self):
        def _act():
            if self._is_minimized:
                self.restore_widget()
                return
            if self.widget_win:
                self.widget_win.deiconify()
            if self.lock_win:
                self.lock_win.deiconify()
            self._toggle_calendar(None)
        self.root.after(0, _act)

    def _on_tray_right_click(self):
        def _popup():
            self._populate_context_menu()
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            self.root.focus_force()
            try:
                self.menu.tk_popup(x, y)
            finally:
                self.menu.grab_release()
        self.root.after(0, _popup)

    def _refresh_display(self):
        info = get_today_info(CUSTOM_OCCASIONS_PATH)
        self.current_jy = info["jy"]
        self.current_jm = info["jm"]
        self.current_jd = info["jd"]

        prev_count = len(self.alarm_store.alarms)
        due_alarms = self.alarm_store.check_due_alarms(info)
        if len(self.alarm_store.alarms) != prev_count:
            if self.alarm_win and self.alarm_win.win and self.alarm_win.win.winfo_exists():
                self.alarm_win._refresh_list()
                self.alarm_win._render_picker_calendar()
            if self.config.get("calendar_expanded"):
                self._render_calendar_month()

        for alarm in due_alarms:
            execute_scheduled_action(
                alarm,
                on_result=lambda _ok, msg: self.root.after(0, lambda m=msg: self._show_toast(m)),
            )
            if alarm.get("show_popup", True) or alarm.get("play_sound", True):
                AnimatedBellPopup(
                    root=self.root,
                    alarm=alarm,
                    font_family=self.config.get("font_family", "Vazir"),
                    on_snooze=lambda a: self.alarm_store.add_snooze(a, 5),
                    on_dismiss=self._on_alarm_dismissed,
                )

        use_fa = self.config.get("persian_digits", False)
        is_locked = bool(self.config.get("locked", False))
        scale = max(70, min(200, int(self.config.get("widget_scale", 100)))) / 100.0

        c_size = max(10, int(self.config.get("clock_font_size", 26) * scale))
        d_size = max(6, int(self.config.get("date_font_size", 11) * scale))
        o_size = max(6, int(self.config.get("occasion_font_size", 9) * scale))

        font_fa = self.config.get("font_family", "Vazir")
        font_clock = self.config.get("clock_font_family", "Vazir")

        # فقط متون پویا را پاک می‌کنیم تا نوار ابزار (toolbar) و وضعیت Hover آیکون‌ها هرگز ریست نشوند
        self.canvas.delete("drawn_text")

        toolbar_x = self.LOCK_OFFSET_X + self.LOCK_BTN_SIZE + 8
        toolbar_y = self.LOCK_OFFSET_Y
        self.canvas.coords(self._win_controls_win_id, toolbar_x, toolbar_y)
        self.win_controls_container.update_idletasks()
        self.btn_container.update_idletasks()
        win_ctrl_right = toolbar_x + self.win_controls_container.winfo_reqwidth()
        dock_w = self.btn_container.winfo_reqwidth()
        dock_h = self.btn_container.winfo_reqheight()
        show_ip_pill = (not is_locked) and bool(self.config.get("ip_monitor_enabled", True))
        ip_pill_w, ip_pill_h = 0, 0
        if show_ip_pill and hasattr(self, "ip_pill_lbl"):
            self.ip_pill_lbl.update_idletasks()
            ip_pill_w = self.ip_pill_lbl.winfo_reqwidth()
            ip_pill_h = self.ip_pill_lbl.winfo_reqheight()
        if not is_locked:
            self.canvas.itemconfigure(self._win_controls_win_id, state="normal")
            self.canvas.itemconfigure(self._toolbar_win_id, state="normal")
            if hasattr(self, "_ip_pill_win_id"):
                self.canvas.itemconfigure(self._ip_pill_win_id, state="normal" if show_ip_pill else "hidden")
        else:
            self.canvas.itemconfigure(self._win_controls_win_id, state="hidden")
            self.canvas.itemconfigure(self._toolbar_win_id, state="hidden")
            if hasattr(self, "_ip_pill_win_id"):
                self.canvas.itemconfigure(self._ip_pill_win_id, state="hidden")

        primary_tz = self.config.get("primary_timezone", "tehran")
        show_utc = bool(self.config.get("show_utc", False))
        show_seconds = bool(self.config.get("show_seconds", False))
        now_utc = datetime.now(timezone.utc)

        if primary_tz == "utc":
            time_str = format_digits(now_utc.strftime("%H:%M:%S"), use_fa)
            date_str = format_digits(f"UTC  •  {now_utc.strftime('%Y-%m-%d')}", use_fa)
            date_fill = self.config.get("accent_color", "#38BDF8")
            utc_line_str = (
                format_digits(f"TEH {info['time_str']}:{info['second']:02d} • {info['date_text']}", use_fa)
                if show_utc
                else ""
            )
        else:
            raw_teh = f"{info['time_str']}:{int(info['second']):02d}" if show_seconds else info["time_str"]
            time_str = format_digits(raw_teh, use_fa)
            date_str = format_digits(info["date_text"], use_fa)
            date_fill = (
                self.config.get("holiday_color", "#F87171")
                if info["is_holiday"]
                else self.config.get("date_color", "#CBD5E1")
            )
            utc_line_str = (
                format_digits(f"UTC {now_utc.strftime('%H:%M:%S')} • {now_utc.strftime('%Y-%m-%d')}", use_fa)
                if show_utc
                else ""
            )

        today_alarms = self.alarm_store.get_events_for_jalali_day(
            info["jy"], info["jm"], info["jd"], info["persian_week_idx"]
        )
        occ_parts = []
        if self._pomodoro_end_ts is not None:
            rem = int(self._pomodoro_end_ts - time.time())
            if rem <= 0:
                lbl_p = self._pomodoro_label or "Deep Work"
                self._pomodoro_end_ts = None
                self._pomodoro_label = ""
                try:
                    AnimatedBellPopup(
                        root=self.root,
                        alarm={
                            "id": "pomodoro-done",
                            "title": f"⏱ پایان تایمر: {lbl_p}",
                            "message": "زمان تعیین‌شده به پایان رسید!",
                            "play_sound": True,
                            "sound_file": self.config.get("default_alarm_sound", "alarm.mp3"),
                        },
                        font_family=self.config.get("font_family", "Vazir"),
                    )
                except Exception:
                    pass
            else:
                occ_parts.append(f"⏱ {rem // 60:02d}:{rem % 60:02d} {self._pomodoro_label}")
        if info["has_occasion"] and info["occasion"]:
            occ_parts.append(info["occasion"])
        for a in today_alarms:
            occ_parts.append(f"⏰ {int(a['hour']):02d}:{int(a['minute']):02d} {a['title']}")
        occ_full = " | ".join(occ_parts)
        if len(occ_full) > 40:
            occ_full = occ_full[:39] + "…"
        occ_str = format_digits(occ_full, use_fa) if occ_full else ""

        tmp_t = self.canvas.create_text(0, 0, text=time_str, font=(font_clock, c_size, "bold"), anchor="nw")
        tmp_d = self.canvas.create_text(0, 0, text=date_str, font=(font_fa, d_size, "bold"), anchor="nw")
        tb_t = self.canvas.bbox(tmp_t) or (0, 0, 90, 32)
        tb_d = self.canvas.bbox(tmp_d) or (0, 0, 140, 20)
        time_w, time_h = tb_t[2] - tb_t[0], tb_t[3] - tb_t[1]
        date_w, date_h = tb_d[2] - tb_d[0], tb_d[3] - tb_d[1]

        utc_w, utc_h = 0, 0
        if utc_line_str:
            tmp_u = self.canvas.create_text(0, 0, text=utc_line_str, font=("Consolas", max(7, o_size), "bold"), anchor="nw")
            tb_u = self.canvas.bbox(tmp_u) or (0, 0, 140, 16)
            utc_w, utc_h = tb_u[2] - tb_u[0], tb_u[3] - tb_u[1]
            self.canvas.delete(tmp_u)

        occ_w, occ_h = 0, 0
        if occ_str:
            tmp_o = self.canvas.create_text(0, 0, text=occ_str, font=(font_fa, o_size), anchor="nw")
            tb_o = self.canvas.bbox(tmp_o) or (0, 0, 120, 16)
            occ_w, occ_h = tb_o[2] - tb_o[0], tb_o[3] - tb_o[1]

        self.canvas.delete(tmp_t, tmp_d)
        if occ_str:
            self.canvas.delete(tmp_o)

        if is_locked:
            top_needed_w = self.LOCK_OFFSET_X + self.LOCK_BTN_SIZE + 10 + time_w + 14
            body_needed_w = max(date_w, utc_w, occ_w) + 24
            target_w = max(top_needed_w, body_needed_w, int(130 * scale))
        else:
            top_needed_w = win_ctrl_right + time_w + 26
            body_needed_w = max(date_w, utc_w, occ_w, dock_w, ip_pill_w) + 28
            target_w = max(int(self.BASE_MIN_W * scale), top_needed_w, body_needed_w)

        right_x = target_w - 14
        cur_y = 8

        if not self.config.get("transparent_bg", False):
            self.canvas.create_rectangle(
                0,
                0,
                target_w,
                2,
                fill=self.config.get("accent_color", "#38BDF8"),
                outline="",
                tags="drawn_text",
            )

        draw_outlined_canvas_text(
            self.canvas,
            right_x,
            cur_y,
            text=time_str,
            font_spec=(font_clock, c_size, "bold"),
            fill=self.config.get("clock_color", "#F8FAFC"),
            outline="#000000",
            anchor="ne",
            justify="right",
            tags="drawn_text",
        )
        cur_y += max(time_h, self.LOCK_BTN_SIZE + 4) + 4

        draw_outlined_canvas_text(
            self.canvas,
            right_x,
            cur_y,
            text=date_str,
            font_spec=(font_fa, d_size, "bold"),
            fill=date_fill,
            outline="#000000",
            anchor="ne",
            justify="right",
            tags="drawn_text",
        )
        cur_y += date_h + 4

        if utc_line_str:
            pill_pad_x = 8
            pill_pad_y = 2
            self.canvas.create_rectangle(
                right_x - utc_w - pill_pad_x * 2,
                cur_y - pill_pad_y,
                right_x,
                cur_y + utc_h + pill_pad_y,
                fill="#0F172A",
                outline="#1E3A5F" if primary_tz != "utc" else "#065F46",
                width=1,
                tags="drawn_text",
            )
            draw_outlined_canvas_text(
                self.canvas,
                right_x - pill_pad_x,
                cur_y,
                text=utc_line_str,
                font_spec=("Consolas", max(7, o_size), "bold"),
                fill="#38BDF8" if primary_tz != "utc" else "#A7F3D0",
                outline="#000000",
                anchor="ne",
                justify="right",
                tags="drawn_text",
            )
            cur_y += utc_h + 7
        else:
            cur_y += 2

        if occ_str:
            draw_outlined_canvas_text(
                self.canvas,
                right_x,
                cur_y,
                text=occ_str,
                font_spec=(font_fa, o_size),
                fill=self.config.get("holiday_color", "#F87171")
                if (info["is_holiday"] and info["has_occasion"])
                else self.config.get("occasion_color", "#94A3B8"),
                outline="#000000",
                anchor="ne",
                justify="right",
                tags="drawn_text",
            )
            cur_y += occ_h + 4

        if not is_locked:
            if show_ip_pill and hasattr(self, "_ip_pill_win_id"):
                cur_y += 3
                pill_x = max(10, (target_w - ip_pill_w) // 2)
                self.canvas.coords(self._ip_pill_win_id, pill_x, cur_y)
                cur_y += ip_pill_h + 3
            cur_y += 4
            dock_x = max(10, (target_w - dock_w) // 2)
            self.canvas.coords(self._toolbar_win_id, dock_x, cur_y)
            cur_y += dock_h + 4

        footer_y = cur_y + 2
        if self._toast_text:
            draw_outlined_canvas_text(
                self.canvas,
                10,
                footer_y,
                text=self._toast_text,
                font_spec=(font_fa, 8, "bold"),
                fill="#10B981",
                outline="#000000",
                anchor="nw",
                tags="drawn_text",
            )
            target_h = footer_y + 18
        elif not is_locked:
            draw_outlined_canvas_text(
                self.canvas,
                10,
                footer_y,
                text="® Shayan Bamyar",
                font_spec=("Segoe UI", 7, "bold"),
                fill="#64748B",
                outline="#000000",
                anchor="nw",
                tags="drawn_text",
            )
            target_h = footer_y + 18
        else:
            # در حالت قفل، فوتر @shayan bamyar حذف می‌شود و ارتفاع به حداقل ممکن کاهش می‌یابد
            target_h = cur_y + 6

        size_changed = (target_w != self._computed_w) or (target_h != self._computed_h)
        self._computed_w = target_w
        self._computed_h = target_h

        if self.widget_win and not getattr(self, "_is_minimized", False) and not self._is_dragging:
            cur_cx = self.widget_win.winfo_x()
            cur_cy = self.widget_win.winfo_y()
            ml, mt, mr, mb = get_monitor_work_area_at(cur_cx + target_w // 2, cur_cy + target_h // 2, self.root)
            if is_locked:
                snap_side = self.config.get("snap_side", "right")
                target_x = (mr - target_w) if snap_side == "right" else ml
                target_y = max(mt, min(cur_cy, mb - target_h))
            else:
                target_x = max(ml, min(cur_cx, mr - target_w))
                target_y = max(mt, min(cur_cy, mb - target_h))

            if size_changed or (cur_cx != target_x) or (cur_cy != target_y):
                self.widget_win.geometry(f"{target_w}x{target_h}+{int(target_x)}+{int(target_y)}")
                if not self.config.get("transparent_bg", False):
                    apply_rounded_corners(self.widget_win, target_w, target_h, radius=10 if is_locked else 16, enabled=True)
                if self.config.get("calendar_expanded"):
                    self._position_calendar_window()
            self._position_lock_window(int(target_x), int(target_y))

        if hasattr(self, "tray") and self.tray:
            self.tray.update_tooltip(self._format_tray_tooltip(info))

        if getattr(self, "clock_replacer", None) is not None:
            try:
                self.clock_replacer.refresh(info)
            except Exception:
                pass
        if getattr(self, "taskbar_clock", None) is not None:
            try:
                self.taskbar_clock.refresh(info)
            except Exception:
                pass
        if getattr(self, "taskbar_proxy", None) is not None:
            self.taskbar_proxy.update_title(
                format_digits(f"{info['time_str'][:5]} | {info['date_text']}", use_fa)
            )

    def _update_clock_loop(self):
        self._refresh_display()
        self.root.after(1000, self._update_clock_loop)

    def _get_ip_pill_fg(self) -> str:
        if getattr(self, "_ip_alert_active", False):
            return "#FCA5A5"
        if self.config.get("ip_lock_enabled", False):
            return "#34D399"
        if self._ip_info.get("ok"):
            return "#38BDF8"
        return "#94A3B8"

    def _update_ip_pill_appearance(self):
        if not hasattr(self, "ip_pill_lbl") or not self.ip_pill_lbl.winfo_exists():
            return
        info = self._ip_info
        is_locked_ip = bool(self.config.get("ip_lock_enabled", False))
        font_fa = self.config.get("font_family", "Vazir")
        if self._ip_alert_active and info.get("ok"):
            city = info.get("city") or info.get("country_code") or "Unknown"
            txt = f"🚨 تغییر لوکیشن: {city} • {info.get('ip', '')}"
            bg = "#450A0A"
            border = "#EF4444"
        elif info.get("ok"):
            city = info.get("city") or "—"
            cc = info.get("country_code") or ""
            loc = f"{city}, {cc}" if cc else city
            prefix = "🔒" if is_locked_ip else "🌐"
            txt = f"{prefix} {loc} • {info.get('ip', '')}"
            bg = self._get_btn_base_bg()
            border = "#10B981" if is_locked_ip else "#2A364F"
        else:
            txt = "🌐 در حال بررسی IP و لوکیشن..."
            bg = self._get_btn_base_bg()
            border = "#2A364F"
        self.ip_pill_lbl.configure(
            text=txt,
            fg=self._get_ip_pill_fg(),
            bg=bg,
            highlightbackground=border,
            font=(font_fa, 8, "bold"),
        )

    def _ip_monitor_loop(self):
        if self.config.get("ip_monitor_enabled", True) or self.config.get("ip_lock_enabled", False):
            self._trigger_ip_check_async()
        try:
            sec = max(3, min(120, int(self.config.get("ip_check_interval", 5))))
        except Exception:
            sec = 5
        self.root.after(sec * 1000, self._ip_monitor_loop)

    def _trigger_ip_check_async(self):
        if self._ip_fetch_inflight:
            return
        self._ip_fetch_inflight = True

        def _worker():
            try:
                res = fetch_ip_geolocation(timeout=4.0)
            except Exception:
                res = {"ok": False}
            try:
                self.root.after(0, lambda r=res: self._handle_ip_result(r))
            except Exception:
                self._ip_fetch_inflight = False

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_ip_result(self, info: dict):
        self._ip_fetch_inflight = False
        if info.get("ok"):
            self._ip_info = info
            try:
                now_teh = datetime.now(TEHRAN_TZ)
                jy, jm, jd = gregorian_to_jalali(now_teh.year, now_teh.month, now_teh.day)
                j_date = f"{jy:04d}/{jm:02d}/{jd:02d}"
            except Exception:
                j_date = ""
            self.ip_history_store.record_if_changed(self._ip_info, jalali_date=j_date)
        changed, reason = check_ip_lock_mismatch(self._ip_info, self.config)
        if changed:
            self._ip_alert_active = True
            mismatch_key = f"{self._ip_info.get('ip')}|{self._ip_info.get('city')}"
            if mismatch_key != self._ip_last_alert_key:
                self._ip_last_alert_key = mismatch_key
                self._fire_ip_mismatch_alarm(reason)
        else:
            if self._ip_info.get("ok"):
                self._ip_alert_active = False
                self._ip_last_alert_key = ""
        self._update_ip_pill_appearance()
        self._refresh_ip_window_labels()
        self._refresh_display()

    def _fire_ip_mismatch_alarm(self, reason: str):
        # بستن آلارم قبلی اگر هنوز باز است
        if self._ip_alert_popup is not None:
            try:
                self._ip_alert_popup.stop_and_close()
            except Exception:
                pass
            self._ip_alert_popup = None

        alarm_payload = {
            "id": "ip-lock-alert",
            "title": "🚨 هشدار تغییر لوکیشن / IP!",
            "message": reason,
            "play_sound": True,
            "sound_file": self.config.get("default_alarm_sound", "alarm.mp3"),
        }
        try:
            self._ip_alert_popup = AnimatedBellPopup(
                self.root,
                alarm_payload,
                font_family=self.config.get("font_family", "Vazir"),
                on_dismiss=lambda _a: setattr(self, "_ip_alert_popup", None),
            )
        except Exception:
            pass
        try:
            if hasattr(self, "tray") and self.tray:
                self.tray.notify("🚨 هشدار تغییر لوکیشن / IP!", reason)
        except Exception:
            pass

    def _lock_ip_location(self, mode: str = "city"):
        if not self._ip_info.get("ok"):
            self._show_toast("ابتدا اطلاعات IP دریافت شود...")
            self._trigger_ip_check_async()
            return
        self.config["ip_lock_enabled"] = True
        self.config["ip_lock_mode"] = mode
        self.config["ip_locked_ip"] = self._ip_info.get("ip", "")
        self.config["ip_locked_city"] = self._ip_info.get("city", "")
        self.config["ip_locked_country"] = self._ip_info.get("country_code", "")
        self._ip_alert_active = False
        self._ip_last_alert_key = ""
        self._save_config()
        self._update_ip_pill_appearance()
        self._refresh_ip_window_labels()
        self._refresh_display()
        if mode == "city":
            self._show_toast(f"🔒 قفل روی شهر {self.config['ip_locked_city']} فعال شد")
        elif mode == "ip":
            self._show_toast(f"🔒 قفل روی IP {self.config['ip_locked_ip']} فعال شد")
        else:
            self._show_toast(f"🔒 قفل روی {self.config['ip_locked_city']} + IP فعال شد")

    def _unlock_ip_location(self):
        self.config["ip_lock_enabled"] = False
        self._ip_alert_active = False
        self._ip_last_alert_key = ""
        self._save_config()
        if self._ip_alert_popup is not None:
            try:
                self._ip_alert_popup.stop_and_close()
            except Exception:
                pass
            self._ip_alert_popup = None
        self._update_ip_pill_appearance()
        self._refresh_ip_window_labels()
        self._refresh_display()
        self._show_toast("🔓 قفل لوکیشن/IP باز شد")

    def _refresh_ip_window_labels(self):
        if not self.ip_win or not self.ip_win.winfo_exists():
            return
        info = self._ip_info
        labels = getattr(self, "_ip_win_labels", None)
        if not labels:
            return
        if info.get("ok"):
            labels["ip"].configure(text=info.get("ip") or "—")
            labels["city"].configure(text=info.get("city") or "—")
            labels["region"].configure(text=info.get("region") or "—")
            cc = info.get("country_code") or ""
            ctry = info.get("country") or "—"
            labels["country"].configure(text=f"{ctry} ({cc})" if cc else ctry)
            labels["isp"].configure(text=info.get("isp") or "—")
            labels["tz"].configure(text=info.get("timezone") or "—")
            labels["checked"].configure(text=info.get("checked_at") or "—")
        else:
            for k in ("ip", "city", "region", "country", "isp", "tz"):
                labels[k].configure(text="در حال دریافت...")
            labels["checked"].configure(text="—")

        if self._ip_alert_active:
            labels["status"].configure(
                text=f"🚨 هشدار! موقعیت تغییر کرده است (قفل روی: {self.config.get('ip_locked_city') or self.config.get('ip_locked_ip')})",
                fg="#FCA5A5",
                bg="#450A0A",
            )
        elif self.config.get("ip_lock_enabled", False):
            mode = self.config.get("ip_lock_mode", "city")
            if mode == "city":
                st = f"🔒 قفل فعال روی شهر: {self.config.get('ip_locked_city') or '—'}"
            elif mode == "ip":
                st = f"🔒 قفل فعال روی IP: {self.config.get('ip_locked_ip') or '—'}"
            else:
                st = f"🔒 قفل فعال روی شهر و IP: {self.config.get('ip_locked_city')} • {self.config.get('ip_locked_ip')}"
            labels["status"].configure(text=st, fg="#6EE7B7", bg="#064E3B")
        else:
            labels["status"].configure(text="🔓 قفل غیرفعال است", fg="#CBD5E1", bg="#1E293B")

        hist_cnt_lbl = labels.get("hist_count")
        hist_box = labels.get("hist_list")
        if hist_cnt_lbl and hist_box:
            entries = self.ip_history_store.get_recent_entries()
            chg_count = self.ip_history_store.get_change_count()
            hist_cnt_lbl.configure(
                text=f"📜 تغییرات ۳ روز اخیر: {chg_count} بار ({len(entries)} موقعیت ثبت‌شده)"
            )
            hist_box.configure(state="normal")
            hist_box.delete("1.0", tk.END)
            if not entries:
                hist_box.insert(tk.END, "هنوز تغییری ثبت نشده است", "meta")
            else:
                for idx, item in enumerate(entries):
                    dt = f"{item.get('jalali_date', '')} {item.get('time_str', '')}".strip()
                    city = item.get("city") or "—"
                    ctry = item.get("country") or item.get("country_code") or "—"
                    ip_s = item.get("ip") or "—"
                    isp = (item.get("isp") or "").strip()
                    isp_part = f"  •  {isp}" if isp else ""
                    hist_box.insert(tk.END, f"🌐 {ip_s}", "ip")
                    hist_box.insert(tk.END, f"   —   {city}, {ctry}\n", "loc")
                    hist_box.insert(tk.END, f"   🕒 {dt}{isp_part}\n", "meta")
                    if idx < len(entries) - 1:
                        hist_box.insert(tk.END, "────────────────────────────────────────\n", "sep")
            hist_box.configure(state="disabled")

    def open_ip_monitor_window(self):
        if self.ip_win and self.ip_win.winfo_exists():
            self.ip_win.lift()
            self.ip_win.focus_force()
            self._trigger_ip_check_async()
            return

        win = tk.Toplevel(self.root)
        self.ip_win = win
        win.title("پایش IP و قفل شهر / لوکیشن")
        win.overrideredirect(True)
        win.configure(bg="#0B1120")
        win.attributes("-topmost", True)
        w, h = 480, 620
        sx = (win.winfo_screenwidth() - w) // 2
        sy = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{sx}+{sy}")
        try:
            apply_rounded_corners(win, w, h, radius=16, enabled=True)
        except Exception:
            pass

        font_fa = self.config.get("font_family", "Vazir")
        outer = tk.Frame(win, bg="#0B1120", highlightbackground="#334155", highlightthickness=1, padx=14, pady=12)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg="#0B1120")
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(
            hdr,
            text="🌐 موقعیت دقیق IP و قفل شهر",
            font=(font_fa, 11, "bold"),
            fg="#38BDF8",
            bg="#0B1120",
        ).pack(side="right")
        close_lbl = tk.Label(
            hdr,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            fg="#94A3B8",
            bg="#0B1120",
            cursor="hand2",
            padx=6,
        )
        close_lbl.pack(side="left")
        close_lbl.bind("<Button-1>", lambda e: win.destroy())

        status_lbl = tk.Label(
            outer,
            text="",
            font=(font_fa, 9, "bold"),
            fg="#CBD5E1",
            bg="#1E293B",
            pady=6,
            padx=8,
            wraplength=340,
            justify="center",
        )
        status_lbl.pack(fill="x", pady=(0, 10))

        card = tk.Frame(outer, bg="#111827", highlightbackground="#1F2937", highlightthickness=1, padx=10, pady=8)
        card.pack(fill="x", pady=(0, 10))

        self._ip_win_labels = {"status": status_lbl}
        rows = [
            ("ip", "IP عمومی:"),
            ("city", "شهر (City):"),
            ("region", "استان / منطقه:"),
            ("country", "کشور:"),
            ("isp", "سرویس‌دهنده (ISP):"),
            ("tz", "تایم‌زون IP:"),
            ("checked", "آخرین بررسی:"),
        ]
        for key, title in rows:
            rf = tk.Frame(card, bg="#111827")
            rf.pack(fill="x", pady=2)
            tk.Label(rf, text=title, font=(font_fa, 9), fg="#94A3B8", bg="#111827", anchor="e").pack(side="right")
            val_lbl = tk.Label(
                rf,
                text="...",
                font=("Consolas", 9, "bold") if key in ("ip", "tz", "checked") else (font_fa, 9, "bold"),
                fg="#F8FAFC" if key != "city" else "#38BDF8",
                bg="#111827",
                anchor="w",
            )
            val_lbl.pack(side="left")
            self._ip_win_labels[key] = val_lbl

        btn_row1 = tk.Frame(outer, bg="#0B1120")
        btn_row1.pack(fill="x", pady=(0, 6))
        tk.Button(
            btn_row1,
            text="🔒 قفل روی شهر فعلی",
            font=(font_fa, 9, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            activebackground="#047857",
            relief="flat",
            cursor="hand2",
            pady=5,
            command=lambda: self._lock_ip_location("city"),
        ).pack(side="right", expand=True, fill="x", padx=(4, 0))
        tk.Button(
            btn_row1,
            text="🔒 قفل روی IP فعلی",
            font=(font_fa, 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            activebackground="#0369A1",
            relief="flat",
            cursor="hand2",
            pady=5,
            command=lambda: self._lock_ip_location("ip"),
        ).pack(side="right", expand=True, fill="x", padx=(0, 4))

        btn_row2 = tk.Frame(outer, bg="#0B1120")
        btn_row2.pack(fill="x", pady=(0, 10))
        tk.Button(
            btn_row2,
            text="🔓 باز کردن قفل",
            font=(font_fa, 9, "bold"),
            bg="#334155",
            fg="#F8FAFC",
            activebackground="#475569",
            relief="flat",
            cursor="hand2",
            pady=4,
            command=self._unlock_ip_location,
        ).pack(side="right", expand=True, fill="x", padx=(4, 0))
        tk.Button(
            btn_row2,
            text="🔄 بررسی فوری",
            font=(font_fa, 9, "bold"),
            bg="#1E293B",
            fg="#38BDF8",
            activebackground="#334155",
            relief="flat",
            cursor="hand2",
            pady=4,
            command=self._trigger_ip_check_async,
        ).pack(side="right", expand=True, fill="x", padx=(0, 4))

        opt_f = tk.Frame(outer, bg="#0B1120")
        opt_f.pack(fill="x")
        show_var = tk.BooleanVar(value=bool(self.config.get("ip_monitor_enabled", True)))

        def _toggle_show():
            self.config["ip_monitor_enabled"] = bool(show_var.get())
            self._save_config()
            self._refresh_display()

        tk.Checkbutton(
            opt_f,
            text="نمایش نوار IP و شهر روی ویجت",
            variable=show_var,
            command=_toggle_show,
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#0B1120",
            selectcolor="#1E293B",
            activebackground="#0B1120",
            activeforeground="#FFFFFF",
        ).pack(side="right")

        iv_f = tk.Frame(opt_f, bg="#0B1120")
        iv_f.pack(side="left")
        tk.Label(iv_f, text="بازه (ثانیه):", font=(font_fa, 8), fg="#94A3B8", bg="#0B1120").pack(side="right", padx=(4, 0))
        iv_var = tk.StringVar(value=str(int(self.config.get("ip_check_interval", 5))))
        for val in ("5", "10", "30"):
            def _set_iv(v=val):
                iv_var.set(v)
                self.config["ip_check_interval"] = int(v)
                self._save_config()
                self._show_toast(f"بازه بررسی IP: هر {v} ثانیه")
            tk.Button(
                iv_f,
                text=val,
                font=("Consolas", 8, "bold"),
                bg="#1E293B",
                fg="#E2E8F0",
                relief="flat",
                padx=5,
                cursor="hand2",
                command=_set_iv,
            ).pack(side="right", padx=1)

        # بخش تاریخچه تغییرات لوکیشن ۳ روز گذشته
        hist_hdr = tk.Frame(outer, bg="#0B1120")
        hist_hdr.pack(fill="x", pady=(10, 4))
        hist_cnt_lbl = tk.Label(
            hist_hdr,
            text="📜 تغییرات ۳ روز اخیر: 0 بار",
            font=(font_fa, 8, "bold"),
            fg="#38BDF8",
            bg="#0B1120",
        )
        hist_cnt_lbl.pack(side="right")

        def _clear_hist():
            self.ip_history_store.clear()
            self._refresh_ip_window_labels()
            self._show_toast("تاریخچه لوکیشن پاک شد")

        tk.Button(
            hist_hdr,
            text="پاک کردن",
            font=(font_fa, 8),
            bg="#1E293B",
            fg="#FCA5A5",
            relief="flat",
            padx=6,
            cursor="hand2",
            command=_clear_hist,
        ).pack(side="left")

        hist_frame = tk.Frame(outer, bg="#111827", highlightbackground="#1F2937", highlightthickness=1)
        hist_frame.pack(fill="both", expand=True)
        hist_scroll = tk.Scrollbar(hist_frame, orient="vertical")
        hist_box = tk.Text(
            hist_frame,
            yscrollcommand=hist_scroll.set,
            font=("Consolas", 9),
            wrap="word",
            bg="#111827",
            fg="#E2E8F0",
            selectbackground="#1E3A5F",
            selectforeground="#FFFFFF",
            bd=0,
            highlightthickness=0,
            padx=6,
            pady=6,
            state="disabled",
            cursor="arrow",
        )
        hist_box.tag_configure("ip", foreground="#38BDF8", font=("Consolas", 9, "bold"))
        hist_box.tag_configure("loc", foreground="#F8FAFC", font=(font_fa, 8))
        hist_box.tag_configure("meta", foreground="#94A3B8", font=("Consolas", 8))
        hist_box.tag_configure("sep", foreground="#1E293B", font=("Consolas", 7))
        hist_scroll.config(command=hist_box.yview)
        hist_scroll.pack(side="left", fill="y")
        hist_box.pack(side="right", fill="both", expand=True, padx=2, pady=2)
        self._ip_win_labels["hist_count"] = hist_cnt_lbl
        self._ip_win_labels["hist_list"] = hist_box

        self._refresh_ip_window_labels()
        self._trigger_ip_check_async()

    def open_dev_ai_hub(self):
        if self.dev_ai_hub and self.dev_ai_hub.win and self.dev_ai_hub.win.winfo_exists():
            self.dev_ai_hub.focus()
            return
        self.dev_ai_hub = DevAiHubWindow(self)

    def start_pomodoro_timer(self, minutes: int = 25, label: str = "Deep Work"):
        mins = max(1, min(240, int(minutes)))
        self._pomodoro_end_ts = time.time() + mins * 60
        self._pomodoro_label = label or "Deep Work"
        self._refresh_display()
        self._show_toast(f"⏱ تایمر {mins} دقیقه‌ای شروع شد")

    def stop_pomodoro_timer(self):
        self._pomodoro_end_ts = None
        self._pomodoro_label = ""
        self._refresh_display()
        self._show_toast("⏱ تایمر متوقف شد")

    def _keep_z_order_loop(self):
        if not self._is_dragging and not getattr(self, "_is_minimized", False) and self.widget_win and self.widget_win.winfo_viewable():
            z_mode = self.config.get("z_mode", "topmost")
            is_locked = bool(self.config.get("locked", False))
            apply_z_order_and_clickthrough(self.widget_win, z_mode, click_through=is_locked)
            if self.lock_win and self.lock_win.winfo_viewable():
                apply_z_order_and_clickthrough(self.lock_win, z_mode, click_through=False)
            if self.cal_win and self.config.get("calendar_expanded"):
                apply_z_order_and_clickthrough(self.cal_win, z_mode, click_through=is_locked)
            # حفظ پنجره کپی زمان/GUID و Tooltipها روی ویجت تا هرگز زیر ویجت نروند
            if self.dev_popup_win and self.dev_popup_win.winfo_exists():
                apply_z_order_and_clickthrough(self.dev_popup_win, "topmost", click_through=False)
            for tip in self._tooltips:
                if tip.tip_win and tip.tip_win.winfo_exists():
                    apply_z_order_and_clickthrough(tip.tip_win, "topmost", click_through=True)
        if getattr(self, "clock_replacer", None) is not None:
            self.clock_replacer.keep_on_top()
        if getattr(self, "taskbar_clock", None) is not None:
            self.taskbar_clock.keep_on_top()
        interval = (
            200
            if (getattr(self, "clock_replacer", None) is not None or getattr(self, "taskbar_clock", None) is not None)
            else 800
        )
        self.root.after(interval, self._keep_z_order_loop)

    def quit_app(self):
        try:
            if getattr(self, "local_api", None) is not None:
                self.local_api.stop()
        except Exception:
            pass
        try:
            if getattr(self, "clock_replacer", None) is not None:
                self.clock_replacer.destroy()
            if getattr(self, "taskbar_clock", None) is not None:
                self.taskbar_clock.destroy()
            if getattr(self, "taskbar_proxy", None) is not None:
                self.taskbar_proxy.destroy()
        except Exception:
            pass
        try:
            if hasattr(self, "tray") and self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PersianClockWidget()
    app.run()
