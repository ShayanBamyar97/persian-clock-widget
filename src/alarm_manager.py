# -*- coding: utf-8 -*-
"""
سیستم مدیریت رویدادها، یادآورها و آلارم‌های هوشمند
ویژگی‌ها:
- انتخابگر تاریخ به صورت تقویم گرافیکی تعاملی با قابلیت انتخاب یک یا چند روز خاص (Multi-Select Calendar)
- حذف خودکار آلارم‌های تاریخ‌دار پس از گذشت زمان آن‌ها (در صورتی که Snooze / به تاخیر نیفتاده باشند)
- ۶ صدای آلارم MP3 داخلی با پیش‌فرض heeeeyyyyy.mp3
- پاپ‌آپ زنگوله طلایی متحرک در مرکز مانیتور
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

import json
import math
import os
import tkinter as tk
from tkinter import ttk
import uuid

try:
    from src.calendar_data import (
        PERSIAN_MONTHS,
        PERSIAN_WEEK_SHORT,
        get_month_calendar,
        get_today_info,
    )
    from src.win_utils import (
        DEFAULT_ALARM_SOUND,
        apply_rounded_corners,
        get_available_alarm_sounds,
        get_resource_path,
        hide_from_taskbar,
        play_mp3_sound,
        stop_mp3_sound,
    )
except ImportError:
    from calendar_data import (
        PERSIAN_MONTHS,
        PERSIAN_WEEK_SHORT,
        get_month_calendar,
        get_today_info,
    )
    from win_utils import (
        DEFAULT_ALARM_SOUND,
        apply_rounded_corners,
        get_available_alarm_sounds,
        get_resource_path,
        hide_from_taskbar,
        play_mp3_sound,
        stop_mp3_sound,
    )

PERSIAN_WEEKDAY_NAMES = [
    "شنبه",
    "یک‌شنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
]


def draw_outlined_canvas_text(
    canvas: tk.Canvas,
    x: int,
    y: int,
    text: str,
    font_spec: tuple,
    fill: str,
    outline: str = "#000000",
    anchor: str = "center",
    justify: str = "center",
    width: int = 0,
    tags: str | tuple = (),
):
    """رسم متن با خط دور مشکی (Stroke) روی بوم Canvas برای خوانایی عالی روی هر پس‌زمینه"""
    offsets = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    for dx, dy in offsets:
        canvas.create_text(
            x + dx,
            y + dy,
            text=text,
            font=font_spec,
            fill=outline,
            anchor=anchor,
            justify=justify,
            width=width,
            tags=tags,
        )
    return canvas.create_text(
        x,
        y,
        text=text,
        font=font_spec,
        fill=fill,
        anchor=anchor,
        justify=justify,
        width=width,
        tags=tags,
    )


def _normalize_alarm_dates(alarm: dict) -> list[str]:
    """استخراج لیست تاریخ‌های شمسی (YYYY/MM/DD) از یک آلارم"""
    dates = alarm.get("dates")
    if isinstance(dates, list) and dates:
        return sorted(set(str(d) for d in dates if d))
    jy = alarm.get("jy")
    jm = alarm.get("jm")
    jd = alarm.get("jd")
    if jy and jm and jd:
        return [f"{int(jy):04d}/{int(jm):02d}/{int(jd):02d}"]
    return []


class AlarmStore:
    """
    ذخیره، بارگذاری و بررسی لحظه‌ای آلارم‌ها و رویدادها
    همراه با حذف خودکار آلارم‌های تاریخ‌دار پس از گذشت زمان آن‌ها (در صورت عدم Snooze)
    """

    def __init__(self, alarms_path: str):
        self.alarms_path = alarms_path
        self.alarms: list[dict] = []
        self.snoozed: list[dict] = []       # لیست آلارم‌های به تاخیر افتاده (Snoozed)
        self.active_ringing_ids: set[str] = set()  # آلارم‌هایی که هم‌اکنون پنجره زنگوله آن‌ها باز است
        self.load()

    def load(self):
        if os.path.exists(self.alarms_path):
            try:
                with open(self.alarms_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.alarms = data
            except Exception:
                self.alarms = []
        else:
            self.alarms = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.alarms_path), exist_ok=True)
            with open(self.alarms_path, "w", encoding="utf-8") as f:
                json.dump(self.alarms, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_or_update(self, alarm_data: dict):
        if not alarm_data.get("sound_file"):
            alarm_data["sound_file"] = DEFAULT_ALARM_SOUND
        aid = alarm_data.get("id")
        if aid:
            for idx, item in enumerate(self.alarms):
                if item.get("id") == aid:
                    self.alarms[idx] = alarm_data
                    self.save()
                    return
        else:
            alarm_data["id"] = str(uuid.uuid4())[:8]
        self.alarms.append(alarm_data)
        self.save()

    def add_alarm(
        self,
        title: str,
        hour: int,
        minute: int,
        repeat: str = "once",
        dates: list[str] | None = None,
        play_sound: bool = True,
        message: str = "",
        action_type: str = "none",
        action_target: str = "",
    ) -> dict:
        """افزودن سریع آلارم یا رویداد زمان‌بندی‌شده (با پشتیبانی از اکشن خودکار)"""
        d_list = list(dates or [])
        jy, jm, jd = 0, 0, 0
        if d_list:
            parts = d_list[0].split("/")
            if len(parts) == 3:
                jy, jm, jd = int(parts[0]), int(parts[1]), int(parts[2])
        alarm_data = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "message": message,
            "hour": int(hour),
            "minute": int(minute),
            "repeat_mode": repeat,
            "dates": d_list,
            "jy": jy,
            "jm": jm,
            "jd": jd,
            "enabled": True,
            "play_sound": bool(play_sound),
            "show_popup": True,
            "sound_file": DEFAULT_ALARM_SOUND,
            "action_type": action_type or "none",
            "action_target": action_target or "",
        }
        self.add_or_update(alarm_data)
        return alarm_data

    def delete(self, alarm_id: str):
        self.alarms = [a for a in self.alarms if a.get("id") != alarm_id]
        self.snoozed = [s for s in self.snoozed if s.get("alarm", {}).get("id") != alarm_id]
        self.save()

    def get_events_for_jalali_day(self, jy: int, jm: int, jd: int, persian_week_idx: int) -> list[dict]:
        """دریافت رویدادها و آلارم‌های مربوط به یک روز خاص برای نمایش در تقویم"""
        target_date_str = f"{jy:04d}/{jm:02d}/{jd:02d}"
        matched = []
        for a in self.alarms:
            if not a.get("enabled", True):
                continue
            mode = a.get("repeat_mode", "once")
            if mode in ("once", "dates"):
                if target_date_str in _normalize_alarm_dates(a):
                    matched.append(a)
            elif mode == "weekly":
                if persian_week_idx in a.get("weekdays", []):
                    matched.append(a)
            elif mode == "daily":
                matched.append(a)
            elif mode == "yearly":
                if f"{jm:02d}-{jd:02d}" in a.get("yearly_days", []):
                    matched.append(a)
        return matched

    def cleanup_expired_alarms(self, today_info: dict) -> bool:
        """
        حذف خودکار آلارم‌های تاریخ‌دار (once / dates) که زمان آن‌ها گذشته است
        و در لیست Snooze یا در حال زنگ زدن نیستند.
        """
        now_date_str = f"{today_info['jy']:04d}/{today_info['jm']:02d}/{today_info['jd']:02d}"
        now_time_tuple = (today_info["hour"], today_info["minute"])

        snoozed_ids = {s.get("alarm", {}).get("id") for s in self.snoozed}
        new_alarms = []
        changed = False

        for a in self.alarms:
            aid = a.get("id")
            mode = a.get("repeat_mode", "once")
            if mode in ("once", "dates"):
                if aid in snoozed_ids or aid in self.active_ringing_ids:
                    new_alarms.append(a)
                    continue

                ah = int(a.get("hour", 0))
                am = int(a.get("minute", 0))
                remaining_dates = []
                for d_str in _normalize_alarm_dates(a):
                    if d_str > now_date_str:
                        remaining_dates.append(d_str)
                    elif d_str == now_date_str and (ah, am) >= now_time_tuple:
                        # اگر در همین دقیقه فعلی است ولی هنوز اجرا نشده، نگه دار تا زنگ بزند
                        if a.get("last_triggered") != f"{now_date_str} {ah:02d}:{am:02d}":
                            remaining_dates.append(d_str)

                if remaining_dates:
                    if remaining_dates != a.get("dates"):
                        a["dates"] = remaining_dates
                        parts = remaining_dates[0].split("/")
                        a["jy"], a["jm"], a["jd"] = int(parts[0]), int(parts[1]), int(parts[2])
                        changed = True
                    new_alarms.append(a)
                else:
                    # تمام تاریخ‌های این آلارم گذشته و به تاخیر هم نیفتاده -> حذف کامل از لیست
                    changed = True
            else:
                new_alarms.append(a)

        if changed:
            self.alarms = new_alarms
            self.save()
        return changed

    def check_due_alarms(self, today_info: dict) -> list[dict]:
        """بررسی آلارم‌هایی که در دقیقه فعلی به وقت تهران باید زنگ بزنند"""
        now_h = today_info["hour"]
        now_m = today_info["minute"]
        jy, jm, jd = today_info["jy"], today_info["jm"], today_info["jd"]
        p_week_idx = today_info["persian_week_idx"]
        today_str = f"{jy:04d}/{jm:02d}/{jd:02d}"
        stamp_key = f"{today_str} {now_h:02d}:{now_m:02d}"

        triggered = []

        # 1. بررسی Snoozeها
        remaining_snoozed = []
        for s in self.snoozed:
            if s.get("target_h") == now_h and s.get("target_m") == now_m and s.get("stamp") != stamp_key:
                s["stamp"] = stamp_key
                triggered.append(s["alarm"])
            else:
                remaining_snoozed.append(s)
        self.snoozed = remaining_snoozed

        # 2. بررسی آلارم‌های اصلی
        changed = False
        for a in self.alarms:
            if not a.get("enabled", True):
                continue
            if int(a.get("hour", -1)) != now_h or int(a.get("minute", -1)) != now_m:
                continue
            if a.get("last_triggered") == stamp_key:
                continue

            mode = a.get("repeat_mode", "once")
            is_match = False
            if mode == "daily":
                is_match = True
            elif mode == "weekly":
                if p_week_idx in a.get("weekdays", []):
                    is_match = True
            elif mode == "yearly":
                if f"{jm:02d}-{jd:02d}" in a.get("yearly_days", []):
                    is_match = True
            elif mode in ("once", "dates"):
                if today_str in _normalize_alarm_dates(a):
                    is_match = True

            if is_match:
                a["last_triggered"] = stamp_key
                if a.get("id"):
                    self.active_ringing_ids.add(a["id"])
                changed = True
                triggered.append(a)

        if changed:
            self.save()

        # پاکسازی آلارم‌های تاریخ‌گذشته که در حال زنگ زدن یا Snooze نیستند
        self.cleanup_expired_alarms(today_info)
        return triggered

    def on_alarm_dismissed(self, alarm: dict):
        """وقتی کاربر آلارم را بدون Snooze می‌بندد، اگر تاریخ‌دار است و تاریخی باقی نمانده از لیست حذف شود"""
        aid = alarm.get("id")
        if aid in self.active_ringing_ids:
            self.active_ringing_ids.discard(aid)
        self.cleanup_expired_alarms(get_today_info())

    def add_snooze(self, alarm: dict, minutes_later: int = 5):
        aid = alarm.get("id")
        if aid in self.active_ringing_ids:
            self.active_ringing_ids.discard(aid)
        info = get_today_info()
        total_m = info["hour"] * 60 + info["minute"] + minutes_later
        th = (total_m // 60) % 24
        tm = total_m % 60
        self.snoozed.append({
            "alarm": alarm,
            "target_h": th,
            "target_m": tm,
            "stamp": "",
        })


class AnimatedBellPopup:
    """
    پنجره هشدار دارک در مرکز مانیتور همراه با زنگوله طلایی متحرک (که تکان می‌خورد و زنگ می‌زند)
    و پخش فایل صوتی MP3 انتخاب‌شده (پیش‌فرض: heeeeyyyyy.mp3)
    """

    def __init__(self, root: tk.Tk, alarm: dict, font_family: str, on_snooze=None, on_dismiss=None):
        self.root = root
        self.alarm = alarm
        self.font_family = font_family
        self.on_snooze = on_snooze
        self.on_dismiss = on_dismiss
        self._running = True
        self._sound_running = bool(alarm.get("play_sound", True))
        self._sound_file = alarm.get("sound_file", DEFAULT_ALARM_SOUND) or DEFAULT_ALARM_SOUND
        self._step = 0

        self.win = tk.Toplevel(root)
        self.win.title("هشدار یادآور و آلارم")
        self.win.overrideredirect(True)
        self.win.configure(bg="#0F172A")
        self.win.attributes("-topmost", True)

        w, h = 410, 320
        sx = (self.win.winfo_screenwidth() - w) // 2
        sy = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{sx}+{sy}")

        try:
            hide_from_taskbar(self.win)
            apply_rounded_corners(self.win, w, h, radius=20, enabled=True)
        except Exception:
            pass

        outer = tk.Frame(
            self.win,
            bg="#0F172A",
            highlightbackground="#F59E0B",
            highlightthickness=2,
            padx=18,
            pady=14,
        )
        outer.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            outer,
            width=370,
            height=225,
            bg="#0F172A",
            highlightthickness=0,
        )
        self.canvas.pack(fill="x")

        time_str = f"{int(alarm.get('hour', 0)):02d}:{int(alarm.get('minute', 0)):02d}"
        title_str = alarm.get("title", "").strip() or "زمان یادآور فرا رسیده است!"

        draw_outlined_canvas_text(
            self.canvas,
            185,
            122,
            text=f"⏰ {time_str}",
            font_spec=(self.font_family, 20, "bold"),
            fill="#FBBF24",
            outline="#000000",
        )

        draw_outlined_canvas_text(
            self.canvas,
            185,
            168,
            text=title_str,
            font_spec=(self.font_family, 12, "bold"),
            fill="#F8FAFC",
            outline="#000000",
            width=340,
        )

        draw_outlined_canvas_text(
            self.canvas,
            185,
            206,
            text=f"🎵 {self._sound_file}",
            font_spec=("Segoe UI", 8),
            fill="#38BDF8",
            outline="#000000",
        )

        btn_row = tk.Frame(outer, bg="#0F172A")
        btn_row.pack(fill="x", pady=(8, 0))

        dismiss_btn = tk.Button(
            btn_row,
            text="✓ متوجه شدم (قطع آلارم)",
            font=(self.font_family, 10, "bold"),
            bg="#10B981",
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._dismiss,
        )
        dismiss_btn.pack(side="right", expand=True, fill="x", padx=(4, 0))

        snooze_btn = tk.Button(
            btn_row,
            text="💤 ۵ دقیقه دیگر (تاخیر)",
            font=(self.font_family, 9, "bold"),
            bg="#334155",
            fg="#E2E8F0",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._snooze,
        )
        snooze_btn.pack(side="left", padx=(0, 4))

        self._animate_bell()
        if self._sound_running:
            play_mp3_sound(self._sound_file, repeat=True)
            self.win.after(60000, stop_mp3_sound)

    def _animate_bell(self):
        if not self._running or not self.win.winfo_exists():
            return

        self.canvas.delete("bell_anim")
        cx, cy = 185, 52
        angle = math.sin(self._step * 0.45) * 0.42

        def rot(px, py):
            dx, dy = px - cx, py - (cy - 22)
            rx = dx * math.cos(angle) - dy * math.sin(angle)
            ry = dx * math.sin(angle) + dy * math.cos(angle)
            return cx + rx, (cy - 22) + ry

        wave_alpha = (self._step % 10) < 6
        if wave_alpha:
            for offset_r in (38, 48):
                self.canvas.create_arc(
                    cx - offset_r, cy - offset_r, cx + offset_r, cy + offset_r,
                    start=135, extent=90, style="arc",
                    outline="#38BDF8", width=2.5, tags="bell_anim"
                )
                self.canvas.create_arc(
                    cx - offset_r, cy - offset_r, cx + offset_r, cy + offset_r,
                    start=-45, extent=90, style="arc",
                    outline="#38BDF8", width=2.5, tags="bell_anim"
                )

        bell_pts_local = [
            (cx - 8, cy - 22),
            (cx + 8, cy - 22),
            (cx + 22, cy + 8),
            (cx + 28, cy + 16),
            (cx - 28, cy + 16),
            (cx - 22, cy + 8),
        ]
        rotated_pts = []
        for px, py in bell_pts_local:
            rx, ry = rot(px, py)
            rotated_pts.extend([rx, ry])

        hx, hy = rot(cx, cy - 26)
        self.canvas.create_oval(
            hx - 6, hy - 6, hx + 6, hy + 6,
            fill="#F59E0B", outline="#000000", width=2, tags="bell_anim"
        )

        clapper_x, clapper_y = rot(cx + math.sin(self._step * 0.45) * 8, cy + 20)
        self.canvas.create_oval(
            clapper_x - 7, clapper_y - 7, clapper_x + 7, clapper_y + 7,
            fill="#D97706", outline="#000000", width=2, tags="bell_anim"
        )

        self.canvas.create_polygon(
            rotated_pts,
            fill="#FBBF24",
            outline="#000000",
            width=2.5,
            smooth=True,
            tags="bell_anim",
        )

        self._step += 1
        self.win.after(35, self._animate_bell)

    def _dismiss(self):
        if self.on_dismiss:
            self.on_dismiss(self.alarm)
        self.close()

    def _snooze(self):
        if self.on_snooze:
            self.on_snooze(self.alarm)
        self.close()

    def close(self):
        self._running = False
        self._sound_running = False
        stop_mp3_sound()
        try:
            if self.win and self.win.winfo_exists():
                self.win.destroy()
        except Exception:
            pass


def format_alarm_schedule_summary(alarm: dict) -> str:
    mode = alarm.get("repeat_mode", "once")
    if mode == "daily":
        return "هر روز"
    elif mode == "yearly":
        ydays = alarm.get("yearly_days", [])
        if not ydays:
            return "سالانه"
        parts_txt = []
        for mmdd in ydays:
            try:
                m_s, d_s = mmdd.split("-")
                m_i, d_i = int(m_s), int(d_s)
                m_name = PERSIAN_MONTHS[m_i] if 1 <= m_i <= 12 else str(m_i)
                parts_txt.append(f"{d_i} {m_name}")
            except Exception:
                parts_txt.append(str(mmdd))
        return "هر سال (" + "، ".join(parts_txt) + ")"
    elif mode == "weekly":
        days = alarm.get("weekdays", [])
        if not days:
            return "هفتگی"
        names = [f"هر {PERSIAN_WEEKDAY_NAMES[d]}" for d in sorted(days) if 0 <= d < 7]
        return "، ".join(names)
    else:
        dates = _normalize_alarm_dates(alarm)
        if not dates:
            return "بدون تاریخ"
        if len(dates) == 1:
            parts = dates[0].split("/")
            jy, jm, jd = int(parts[0]), int(parts[1]), int(parts[2])
            m_name = PERSIAN_MONTHS[jm] if 1 <= jm <= 12 else str(jm)
            return f"{jd} {m_name} {jy}"
        return f"{len(dates)} تاریخ انتخاب‌شده ({'، '.join(dates[:3])}{'...' if len(dates) > 3 else ''})"


class AlarmManagerWindow:
    """
    پنجره گرافیکی حرفه‌ای برای افزودن، ویرایش، انتخاب صدای آلارم MP3 و حذف رویدادها
    همراه با تقویم گرافیکی تعاملی جهت انتخاب یک یا چند روز خاص
    """

    def __init__(
        self,
        root: tk.Tk,
        store: AlarmStore,
        font_family: str,
        initial_jalali: tuple[int, int, int],
        on_change_callback=None,
    ):
        self.root = root
        self.store = store
        self.font_family = font_family
        self.initial_jy, self.initial_jm, self.initial_jd = initial_jalali
        self.on_change_callback = on_change_callback
        self.editing_id: str | None = None

        # وضعیت تقویم تعاملی داخل فرم رویدادها (قابلیت انتخاب چند روز خاص)
        self.cal_jy = self.initial_jy
        self.cal_jm = self.initial_jm
        self.selected_dates: set[str] = {
            f"{self.initial_jy:04d}/{self.initial_jm:02d}/{self.initial_jd:02d}"
        }

        self.win = tk.Toplevel(root)
        self.win.title("مدیریت رویدادها و آلارم‌ها")
        self.win.configure(bg="#0F172A")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)

        ico_path = get_resource_path(os.path.join("assets", "icons", "app_icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.win.iconbitmap(ico_path)
            except Exception:
                pass

        w, h = 560, 760
        sx = (self.win.winfo_screenwidth() - w) // 2
        sy = max(10, (self.win.winfo_screenheight() - h) // 2)
        self.win.geometry(f"{w}x{h}+{sx}+{sy}")

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._refresh_list()

    def _on_close(self):
        stop_mp3_sound()
        self.win.destroy()

    def _build_ui(self):
        main = tk.Frame(self.win, bg="#0F172A", padx=16, pady=12)
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="⏰ مدیریت رویدادها، یادآورها و آلارم‌ها",
            font=(self.font_family, 12, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 6))

        self.form_frame = tk.LabelFrame(
            main,
            text=" ➕ ثبت رویداد / آلارم جدید ",
            font=(self.font_family, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=12,
            pady=8,
        )
        self.form_frame.pack(fill="x", pady=(0, 8))

        # 1. عنوان و متن رویداد
        row1 = tk.Frame(self.form_frame, bg="#1E293B")
        row1.pack(fill="x", pady=2)
        tk.Label(
            row1,
            text="متن اعلان / عنوان رویداد:",
            font=(self.font_family, 9),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right", padx=(6, 0))

        self.title_entry = tk.Entry(
            row1,
            font=(self.font_family, 9),
            bg="#0F172A",
            fg="#F8FAFC",
            insertbackground="#38BDF8",
            justify="right",
            relief="flat",
        )
        self.title_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.title_entry.insert(0, "یادآوری مهم")

        # 2. ساعت و دقیقه به وقت تهران
        row2 = tk.Frame(self.form_frame, bg="#1E293B")
        row2.pack(fill="x", pady=4)
        tk.Label(
            row2,
            text="ساعت هشدار (به وقت تهران):",
            font=(self.font_family, 9),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right", padx=(6, 0))

        now_info = get_today_info()
        time_box = tk.Frame(row2, bg="#1E293B")
        time_box.pack(side="left")

        self.hour_spin = tk.Spinbox(
            time_box,
            from_=0,
            to=23,
            format="%02.0f",
            width=4,
            font=("Segoe UI", 10, "bold"),
            bg="#0F172A",
            fg="#38BDF8",
            buttonbackground="#334155",
            justify="center",
        )
        self.hour_spin.delete(0, "end")
        self.hour_spin.insert(0, f"{now_info['hour']:02d}")
        self.hour_spin.pack(side="left")

        tk.Label(time_box, text=" : ", font=("Segoe UI", 10, "bold"), fg="#F8FAFC", bg="#1E293B").pack(side="left")

        self.min_spin = tk.Spinbox(
            time_box,
            from_=0,
            to=59,
            format="%02.0f",
            width=4,
            font=("Segoe UI", 10, "bold"),
            bg="#0F172A",
            fg="#38BDF8",
            buttonbackground="#334155",
            justify="center",
        )
        self.min_spin.delete(0, "end")
        self.min_spin.insert(0, f"{(now_info['minute'] + 1) % 60:02d}")
        self.min_spin.pack(side="left")

        # 3. نوع تکرار (انتخاب از روی تقویم / هر روز / روزهای هفته)
        row3 = tk.Frame(self.form_frame, bg="#1E293B")
        row3.pack(fill="x", pady=3)
        tk.Label(
            row3,
            text="نوع زمان‌بندی:",
            font=(self.font_family, 9),
            fg="#CBD5E1",
            bg="#1E293B",
        ).pack(side="right")

        self.repeat_var = tk.StringVar(value="dates")
        for val, lbl_t in [
            ("dates", "📅 انتخاب روز(ها) از تقویم"),
            ("daily", "🔄 هر روز"),
            ("weekly", "📆 روزهای خاص هفته (مثلاً هر دوشنبه)"),
        ]:
            tk.Radiobutton(
                row3,
                text=lbl_t,
                variable=self.repeat_var,
                value=val,
                command=self._update_schedule_subframe,
                font=(self.font_family, 8, "bold"),
                fg="#F8FAFC",
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
            ).pack(side="right", padx=3)

        self.schedule_subframe = tk.Frame(self.form_frame, bg="#1E293B")
        self.schedule_subframe.pack(fill="x", pady=4)

        # الف) تقویم گرافیکی تعاملی با قابلیت انتخاب چند روز (Multi-Select Mini Calendar)
        self.calendar_picker_frame = tk.Frame(
            self.schedule_subframe,
            bg="#0F172A",
            highlightbackground="#334155",
            highlightthickness=1,
            padx=10,
            pady=6,
        )

        cal_nav = tk.Frame(self.calendar_picker_frame, bg="#0F172A")
        cal_nav.pack(fill="x", pady=(0, 4))

        next_btn = tk.Label(
            cal_nav, text="‹ ماه بعد", font=(self.font_family, 8, "bold"),
            fg="#F8FAFC", bg="#1E293B", padx=8, pady=2, cursor="hand2"
        )
        next_btn.pack(side="left")
        next_btn.bind("<Button-1>", lambda e: self._change_picker_month(1))

        clear_dates_btn = tk.Label(
            cal_nav, text="پاک کردن انتخاب‌ها", font=(self.font_family, 7),
            fg="#F87171", bg="#1E293B", padx=6, pady=2, cursor="hand2"
        )
        clear_dates_btn.pack(side="left", padx=4)
        clear_dates_btn.bind("<Button-1>", lambda e: self._clear_selected_dates())

        prev_btn = tk.Label(
            cal_nav, text="ماه قبل ›", font=(self.font_family, 8, "bold"),
            fg="#F8FAFC", bg="#1E293B", padx=8, pady=2, cursor="hand2"
        )
        prev_btn.pack(side="right")
        prev_btn.bind("<Button-1>", lambda e: self._change_picker_month(-1))

        self.picker_title_lbl = tk.Label(
            cal_nav, text="", font=(self.font_family, 9, "bold"),
            fg="#38BDF8", bg="#0F172A"
        )
        self.picker_title_lbl.pack(side="right", expand=True)

        # سرستون روزهای هفته در تقویم انتخابگر
        wk_row = tk.Frame(self.calendar_picker_frame, bg="#0F172A")
        wk_row.pack(fill="x")
        for col_idx in range(7):
            p_idx = 6 - col_idx
            tk.Label(
                wk_row,
                text=PERSIAN_WEEK_SHORT[p_idx],
                font=(self.font_family, 8, "bold"),
                fg="#F87171" if p_idx == 6 else "#94A3B8",
                bg="#0F172A",
                width=4,
            ).grid(row=0, column=col_idx, sticky="nsew", padx=1)
            wk_row.grid_columnconfigure(col_idx, weight=1)

        # شبکه روزهای تقویم انتخابگر
        self.picker_grid = tk.Frame(self.calendar_picker_frame, bg="#0F172A")
        self.picker_grid.pack(fill="x", pady=2)
        self.picker_cells: list[tk.Label] = []
        for r in range(6):
            self.picker_grid.grid_rowconfigure(r, weight=1)
            for c in range(7):
                self.picker_grid.grid_columnconfigure(c, weight=1)
                lbl = tk.Label(
                    self.picker_grid,
                    text="",
                    font=("Segoe UI", 8, "bold"),
                    fg="#F8FAFC",
                    bg="#1E293B",
                    width=4,
                    pady=2,
                    cursor="hand2",
                )
                lbl.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                self.picker_cells.append(lbl)

        self.selected_dates_summary_lbl = tk.Label(
            self.calendar_picker_frame,
            text="",
            font=(self.font_family, 8),
            fg="#10B981",
            bg="#0F172A",
            anchor="e",
            justify="right",
        )
        self.selected_dates_summary_lbl.pack(fill="x", pady=(3, 0))

        # ب) فریم انتخاب روزهای هفته (شنبه تا جمعه)
        self.weekly_frame = tk.Frame(self.schedule_subframe, bg="#1E293B")
        self.weekday_vars: list[tk.BooleanVar] = []
        for idx, w_name in enumerate(PERSIAN_WEEKDAY_NAMES):
            var = tk.BooleanVar(value=(idx == now_info["persian_week_idx"]))
            self.weekday_vars.append(var)
            tk.Checkbutton(
                self.weekly_frame,
                text=w_name,
                variable=var,
                font=(self.font_family, 8),
                fg="#F8FAFC",
                bg="#1E293B",
                selectcolor="#0F172A",
                activebackground="#1E293B",
                padx=2,
            ).pack(side="right")

        self._render_picker_calendar()
        self._update_schedule_subframe()

        # 4. انتخاب صدای آلارم MP3 (پیش‌فرض: heeeeyyyyy.mp3)
        sound_row = tk.Frame(self.form_frame, bg="#1E293B")
        sound_row.pack(fill="x", pady=4)
        tk.Label(
            sound_row,
            text="🎵 انتخاب صدای آلارم:",
            font=(self.font_family, 9, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
        ).pack(side="right", padx=(6, 0))

        available_sounds = get_available_alarm_sounds()
        self.sound_cb = ttk.Combobox(
            sound_row,
            values=available_sounds,
            state="readonly",
            width=22,
        )
        if DEFAULT_ALARM_SOUND in available_sounds:
            self.sound_cb.set(DEFAULT_ALARM_SOUND)
        elif available_sounds:
            self.sound_cb.current(0)
        self.sound_cb.pack(side="left", padx=(0, 6))

        tk.Button(
            sound_row,
            text="▶ تست صدا",
            font=(self.font_family, 8, "bold"),
            bg="#065F46",
            fg="#A7F3D0",
            relief="flat",
            padx=8,
            cursor="hand2",
            command=lambda: play_mp3_sound(self.sound_cb.get(), repeat=False),
        ).pack(side="left", padx=2)

        tk.Button(
            sound_row,
            text="⏹ توقف",
            font=(self.font_family, 8),
            bg="#7F1D1D",
            fg="#FECACA",
            relief="flat",
            padx=6,
            cursor="hand2",
            command=stop_mp3_sound,
        ).pack(side="left", padx=2)

        # 5. گزینه‌های فعال بودن صدا و پاپ‌آپ زنگوله
        row4 = tk.Frame(self.form_frame, bg="#1E293B")
        row4.pack(fill="x", pady=(2, 4))

        self.sound_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row4,
            text="🔊 پخش صدای آلارم",
            variable=self.sound_var,
            font=(self.font_family, 8, "bold"),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(side="right", padx=6)

        self.popup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row4,
            text="🔔 نمایش زنگوله متحرک و متن در مرکز مانیتور",
            variable=self.popup_var,
            font=(self.font_family, 8, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(side="right", padx=6)

        btn_bar = tk.Frame(self.form_frame, bg="#1E293B")
        btn_bar.pack(fill="x", pady=(4, 0))

        self.save_btn = tk.Button(
            btn_bar,
            text="➕ افزودن به لیست آلارم‌ها",
            font=(self.font_family, 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._save_alarm_from_form,
        )
        self.save_btn.pack(side="right")

        self.cancel_edit_btn = tk.Button(
            btn_bar,
            text="انصراف از ویرایش",
            font=(self.font_family, 8),
            bg="#475569",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._reset_form,
        )

        tk.Button(
            btn_bar,
            text="🔔 پیش‌نمایش زنگوله + صدا",
            font=(self.font_family, 8),
            bg="#334155",
            fg="#FBBF24",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._test_current_form,
        ).pack(side="left")

        list_label_frame = tk.LabelFrame(
            main,
            text=" 📋 لیست آلارم‌ها و رویدادهای فعال ",
            font=(self.font_family, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            bd=1,
            padx=8,
            pady=6,
        )
        list_label_frame.pack(fill="both", expand=True)

        self.list_canvas = tk.Canvas(list_label_frame, bg="#1E293B", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_label_frame, orient="vertical", command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg="#1E293B")

        self.list_inner.bind(
            "<Configure>",
            lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")),
        )
        self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw", width=500)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)

        self.list_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = tk.Frame(main, bg="#0F172A")
        footer.pack(fill="x", pady=(6, 0))
        tk.Label(
            footer,
            text="® Shayan Bamyar",
            font=("Segoe UI", 8, "bold"),
            fg="#64748B",
            bg="#0F172A",
        ).pack(side="left")

        tk.Button(
            footer,
            text="بستن پنجره",
            font=(self.font_family, 9),
            bg="#334155",
            fg="#F8FAFC",
            relief="flat",
            padx=14,
            pady=3,
            cursor="hand2",
            command=self._on_close,
        ).pack(side="right")

    # -----------------------------------------------------------------------
    # منطق تقویم گرافیکی تعاملی با قابلیت انتخاب چند روز خاص
    # -----------------------------------------------------------------------
    def _change_picker_month(self, delta: int):
        m = self.cal_jm + delta
        y = self.cal_jy
        if m > 12:
            m = 1
            y += 1
        elif m < 1:
            m = 12
            y -= 1
        self.cal_jy, self.cal_jm = y, m
        self._render_picker_calendar()

    def _clear_selected_dates(self):
        today = get_today_info()
        self.selected_dates = {f"{today['jy']:04d}/{today['jm']:02d}/{today['jd']:02d}"}
        self._render_picker_calendar()

    def _toggle_picker_date(self, date_str: str):
        if date_str in self.selected_dates:
            if len(self.selected_dates) > 1:
                self.selected_dates.remove(date_str)
        else:
            self.selected_dates.add(date_str)
        self._render_picker_calendar()

    def _render_picker_calendar(self):
        m_data = get_month_calendar(self.cal_jy, self.cal_jm)
        self.picker_title_lbl.configure(
            text=f"{m_data['header_title']}  (با کلیک یک یا چند روز را انتخاب کنید)"
        )

        for cell in self.picker_cells:
            cell.configure(text="", bg="#0F172A", cursor="arrow")
            cell.unbind("<Button-1>")

        first_w = m_data["first_day_week_idx"]
        for d_info in m_data["days"]:
            d = d_info["jd"]
            offset = first_w + (d - 1)
            row = offset // 7
            p_col = offset % 7
            g_col = 6 - p_col
            idx = row * 7 + g_col
            if idx >= len(self.picker_cells):
                continue

            cell = self.picker_cells[idx]
            d_str = f"{self.cal_jy:04d}/{self.cal_jm:02d}/{d:02d}"
            is_sel = d_str in self.selected_dates

            if is_sel:
                bg_c = "#10B981"  # سبز زمردی برای روزهای انتخاب‌شده
                fg_c = "#FFFFFF"
            else:
                bg_c = "#1E293B"
                fg_c = "#F87171" if d_info["is_holiday"] else "#E2E8F0"

            cell.configure(text=str(d), bg=bg_c, fg=fg_c, cursor="hand2")
            cell.bind("<Button-1>", lambda e, ds=d_str: self._toggle_picker_date(ds))

        sorted_d = sorted(self.selected_dates)
        summary = f"✓ روزهای انتخاب‌شده ({len(sorted_d)} روز):  " + " ، ".join(sorted_d[:4])
        if len(sorted_d) > 4:
            summary += f" و {len(sorted_d) - 4} روز دیگر"
        self.selected_dates_summary_lbl.configure(text=summary)

    def _update_schedule_subframe(self):
        self.calendar_picker_frame.pack_forget()
        self.weekly_frame.pack_forget()
        mode = self.repeat_var.get()
        if mode in ("once", "dates"):
            self.calendar_picker_frame.pack(fill="x")
        elif mode == "weekly":
            self.weekly_frame.pack(fill="x")

    def _collect_form_data(self) -> dict:
        try:
            h = max(0, min(23, int(self.hour_spin.get())))
        except ValueError:
            h = 12
        try:
            m = max(0, min(59, int(self.min_spin.get())))
        except ValueError:
            m = 0

        sorted_dates = sorted(self.selected_dates)
        if not sorted_dates:
            sorted_dates = [f"{self.initial_jy:04d}/{self.initial_jm:02d}/{self.initial_jd:02d}"]
        first_parts = sorted_dates[0].split("/")
        jy, jm, jd = int(first_parts[0]), int(first_parts[1]), int(first_parts[2])

        weekdays = [i for i, v in enumerate(self.weekday_vars) if v.get()]
        title = self.title_entry.get().strip() or "یادآور"
        sound_file = self.sound_cb.get() or DEFAULT_ALARM_SOUND

        return {
            "id": self.editing_id,
            "title": title,
            "hour": h,
            "minute": m,
            "repeat_mode": self.repeat_var.get(),
            "dates": sorted_dates,
            "jy": jy,
            "jm": jm,
            "jd": jd,
            "weekdays": weekdays,
            "sound_file": sound_file,
            "play_sound": bool(self.sound_var.get()),
            "show_popup": bool(self.popup_var.get()),
            "enabled": True,
            "last_triggered": "",
        }

    def _save_alarm_from_form(self):
        stop_mp3_sound()
        data = self._collect_form_data()
        self.store.add_or_update(data)
        self._reset_form()
        self._refresh_list()
        if self.on_change_callback:
            self.on_change_callback()

    def _test_current_form(self):
        data = self._collect_form_data()
        AnimatedBellPopup(self.root, data, self.font_family)

    def _reset_form(self):
        self.editing_id = None
        self.form_frame.configure(text=" ➕ ثبت رویداد / آلارم جدید ")
        self.save_btn.configure(text="➕ افزودن به لیست آلارم‌ها", bg="#0284C7")
        self.cancel_edit_btn.pack_forget()
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, "یادآوری مهم")
        self.sound_cb.set(DEFAULT_ALARM_SOUND)
        self.selected_dates = {
            f"{self.initial_jy:04d}/{self.initial_jm:02d}/{self.initial_jd:02d}"
        }
        self._render_picker_calendar()

    def _load_into_form(self, alarm: dict):
        self.editing_id = alarm.get("id")
        self.form_frame.configure(text=" ✏️ در حال ویرایش آلارم انتخاب‌شده ")
        self.save_btn.configure(text="💾 ذخیره تغییرات", bg="#10B981")
        self.cancel_edit_btn.pack(side="right", padx=6)

        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, alarm.get("title", ""))

        self.hour_spin.delete(0, "end")
        self.hour_spin.insert(0, f"{int(alarm.get('hour', 0)):02d}")
        self.min_spin.delete(0, "end")
        self.min_spin.insert(0, f"{int(alarm.get('minute', 0)):02d}")

        mode = alarm.get("repeat_mode", "dates")
        if mode == "once":
            mode = "dates"
        self.repeat_var.set(mode)

        norm_dates = _normalize_alarm_dates(alarm)
        if norm_dates:
            self.selected_dates = set(norm_dates)
            first_p = norm_dates[0].split("/")
            self.cal_jy, self.cal_jm = int(first_p[0]), int(first_p[1])
        self._render_picker_calendar()

        w_days = set(alarm.get("weekdays", []))
        for idx, var in enumerate(self.weekday_vars):
            var.set(idx in w_days)

        self.sound_cb.set(alarm.get("sound_file", DEFAULT_ALARM_SOUND) or DEFAULT_ALARM_SOUND)
        self.sound_var.set(bool(alarm.get("play_sound", True)))
        self.popup_var.set(bool(alarm.get("show_popup", True)))
        self._update_schedule_subframe()

    def _toggle_item_enabled(self, alarm: dict):
        alarm["enabled"] = not alarm.get("enabled", True)
        self.store.save()
        self._refresh_list()
        if self.on_change_callback:
            self.on_change_callback()

    def _delete_item(self, alarm_id: str):
        self.store.delete(alarm_id)
        if self.editing_id == alarm_id:
            self._reset_form()
        self._refresh_list()
        if self.on_change_callback:
            self.on_change_callback()

    def _refresh_list(self):
        for child in self.list_inner.winfo_children():
            child.destroy()

        if not self.store.alarms:
            tk.Label(
                self.list_inner,
                text="هیچ رویداد یا آلارم فعالی در لیست وجود ندارد.",
                font=(self.font_family, 9),
                fg="#64748B",
                bg="#1E293B",
                pady=18,
            ).pack(fill="x")
            return

        for alarm in self.store.alarms:
            card = tk.Frame(
                self.list_inner,
                bg="#0F172A",
                highlightbackground="#334155",
                highlightthickness=1,
                padx=8,
                pady=6,
            )
            card.pack(fill="x", pady=3, padx=2)

            is_en = alarm.get("enabled", True)
            t_str = f"{int(alarm.get('hour', 0)):02d}:{int(alarm.get('minute', 0)):02d}"
            sched_str = format_alarm_schedule_summary(alarm)
            snd_name = alarm.get("sound_file", DEFAULT_ALARM_SOUND)
            icons = []
            if alarm.get("play_sound", True):
                icons.append(f"🔊({snd_name})")
            if alarm.get("show_popup", True):
                icons.append("🔔")
            icons_str = " ".join(icons)

            tk.Button(
                card,
                text="🗑 حذف",
                font=(self.font_family, 8),
                bg="#7F1D1D",
                fg="#FECACA",
                relief="flat",
                padx=6,
                cursor="hand2",
                command=lambda aid=alarm["id"]: self._delete_item(aid),
            ).pack(side="left", padx=2)

            tk.Button(
                card,
                text="✏️ ویرایش",
                font=(self.font_family, 8),
                bg="#1E3A8A",
                fg="#BFDBFE",
                relief="flat",
                padx=6,
                cursor="hand2",
                command=lambda a=alarm: self._load_into_form(a),
            ).pack(side="left", padx=2)

            tk.Button(
                card,
                text="فعال" if is_en else "غیرفعال",
                font=(self.font_family, 8, "bold"),
                bg="#065F46" if is_en else "#334155",
                fg="#A7F3D0" if is_en else "#94A3B8",
                relief="flat",
                padx=6,
                cursor="hand2",
                command=lambda a=alarm: self._toggle_item_enabled(a),
            ).pack(side="left", padx=2)

            info_box = tk.Frame(card, bg="#0F172A")
            info_box.pack(side="right", fill="x", expand=True, padx=4)

            tk.Label(
                info_box,
                text=f"{t_str}  |  {alarm.get('title', '')}",
                font=(self.font_family, 9, "bold"),
                fg="#F8FAFC" if is_en else "#64748B",
                bg="#0F172A",
                anchor="e",
            ).pack(fill="x")

            tk.Label(
                info_box,
                text=f"زمان‌بندی: {sched_str}  |  {icons_str}",
                font=(self.font_family, 8),
                fg="#38BDF8" if is_en else "#475569",
                bg="#0F172A",
                anchor="e",
            ).pack(fill="x")
