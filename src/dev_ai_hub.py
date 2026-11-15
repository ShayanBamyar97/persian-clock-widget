# -*- coding: utf-8 -*-
"""
پنجره یکپارچه ابزارهای هوشمند برنامه‌نویسی، زمان‌بندی و اتصال به AI (نسخه ۲)
شامل ۵ تب:
1. مبدل Timestamp / ISO / شمسی + دیکدر آفلاین JWT + تولید GUID / ULID / NanoID
2. دستیار Cron (توضیح فارسی + ۵ اجرای بعدی تهران و UTC)
3. برنامه‌ریز جلسات تیمی (تهران ⇄ UTC / لندن / برلین / دبی / نیویورک)
4. تایمر پومودورو + زمان‌بند اکشن سر ساعت (URL / Webhook / Command)
5. سرور محلی AI (HTTP REST + MCP JSON-RPC) و کپی کانفیگ

طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

from datetime import datetime, timedelta
import json
import time
import tkinter as tk
from tkinter import ttk
import urllib.request

try:
    from src.calendar_data import TEHRAN_TZ, gregorian_to_jalali
    from src.dev_tools import (
        CRON_PRESETS,
        convert_tehran_meeting_time,
        decode_jwt_offline,
        describe_cron_fa,
        generate_guid,
        generate_nanoid,
        generate_ulid,
        next_cron_runs,
        parse_any_time_input,
    )
    from src.win_utils import apply_rounded_corners
except ImportError:
    from calendar_data import TEHRAN_TZ, gregorian_to_jalali
    from dev_tools import (
        CRON_PRESETS,
        convert_tehran_meeting_time,
        decode_jwt_offline,
        describe_cron_fa,
        generate_guid,
        generate_nanoid,
        generate_ulid,
        next_cron_runs,
        parse_any_time_input,
    )
    from win_utils import apply_rounded_corners


class DevAiHubWindow:
    """پنجره ابزارهای برنامه‌نویسی، زمان‌بندی هوشمند و اتصال به AI"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.win: tk.Toplevel | None = None
        self._build()

    def focus(self):
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()

    def _copy(self, text: str, label: str = "متن"):
        self.app._copy_to_clipboard(text, f"✓ {label} کپی شد!")

    def _build(self):
        win = tk.Toplevel(self.root)
        self.win = win
        win.title("ابزارهای هوشمند برنامه‌نویسی و AI (v2.0)")
        win.overrideredirect(True)
        win.configure(bg="#0B1120")
        win.attributes("-topmost", True)

        w, h = 640, 620
        sx = (win.winfo_screenwidth() - w) // 2
        sy = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{sx}+{sy}")
        try:
            apply_rounded_corners(win, w, h, radius=16, enabled=True)
        except Exception:
            pass

        font_fa = self.app.config.get("font_family", "Vazir")
        outer = tk.Frame(win, bg="#0B1120", highlightbackground="#334155", highlightthickness=1, padx=12, pady=10)
        outer.pack(fill="both", expand=True)

        # هدر پنجره + امکان درگ
        hdr = tk.Frame(outer, bg="#0B1120")
        hdr.pack(fill="x", pady=(0, 8))
        title_lbl = tk.Label(
            hdr,
            text="⚡ ابزارهای هوشمند برنامه‌نویسی، زمان‌بندی و AI (v2.0)",
            font=(font_fa, 10, "bold"),
            fg="#38BDF8",
            bg="#0B1120",
        )
        title_lbl.pack(side="right")

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

        drag_pos = {"x": 0, "y": 0}

        def _d_start(e):
            drag_pos["x"] = e.x_root - win.winfo_x()
            drag_pos["y"] = e.y_root - win.winfo_y()

        def _d_move(e):
            win.geometry(f"{w}x{h}+{e.x_root - drag_pos['x']}+{e.y_root - drag_pos['y']}")

        for dw in (hdr, title_lbl):
            dw.bind("<ButtonPress-1>", _d_start)
            dw.bind("<B1-Motion>", _d_move)

        style = ttk.Style(win)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("DevHub.TNotebook", background="#0B1120", borderwidth=0)
        style.configure(
            "DevHub.TNotebook.Tab",
            background="#1E293B",
            foreground="#CBD5E1",
            padding=(8, 5),
            font=(font_fa, 8, "bold"),
        )
        style.map(
            "DevHub.TNotebook.Tab",
            background=[("selected", "#0284C7")],
            foreground=[("selected", "#FFFFFF")],
        )

        nb = ttk.Notebook(outer, style="DevHub.TNotebook")
        nb.pack(fill="both", expand=True)

        t1 = tk.Frame(nb, bg="#0F172A", padx=10, pady=10)
        t2 = tk.Frame(nb, bg="#0F172A", padx=10, pady=10)
        t3 = tk.Frame(nb, bg="#0F172A", padx=10, pady=10)
        t4 = tk.Frame(nb, bg="#0F172A", padx=10, pady=10)
        t5 = tk.Frame(nb, bg="#0F172A", padx=10, pady=10)

        nb.add(t1, text="🕒 Timestamp & JWT")
        nb.add(t2, text="⚙ دستیار Cron")
        nb.add(t3, text="🌍 جلسات")
        nb.add(t4, text="⏱ پومودورو و اکشن")
        nb.add(t5, text="🤖 اتصال به AI")

        self._build_tab_converter_jwt(t1, font_fa)
        self._build_tab_cron(t2, font_fa)
        self._build_tab_meetings(t3, font_fa)
        self._build_tab_pomodoro_actions(t4, font_fa)
        self._build_tab_ai_mcp(t5, font_fa)

    # ── تب ۱: مبدل Timestamp / ISO / شمسی + دیکدر آفلاین JWT + IDها ──
    def _build_tab_converter_jwt(self, parent: tk.Frame, font_fa: str):
        tk.Label(
            parent,
            text="تبدیل سریع Unix Timestamp (ثانیه/میلی‌ثانیه)، ISO-8601 یا تاریخ شمسی (مثلاً 1405/08/24 14:30):",
            font=(font_fa, 8, "bold"),
            fg="#E2E8F0",
            bg="#0F172A",
            anchor="e",
            justify="right",
            wraplength=580,
        ).pack(fill="x", pady=(0, 4))

        row = tk.Frame(parent, bg="#0F172A")
        row.pack(fill="x", pady=(0, 6))
        ts_entry = tk.Entry(row, font=("Consolas", 9), bg="#1E293B", fg="#F8FAFC", insertbackground="#38BDF8", relief="flat")
        ts_entry.pack(side="right", fill="x", expand=True, ipady=4, padx=(6, 0))
        ts_entry.insert(0, str(int(datetime.now().timestamp())))

        res_box = tk.Frame(parent, bg="#111827", highlightbackground="#1F2937", highlightthickness=1, padx=8, pady=6)
        res_box.pack(fill="x", pady=(0, 8))
        ts_labels: dict[str, tk.Label] = {}
        for k, title in (
            ("jalali", "شمسی (تهران):"),
            ("tehran", "میلادی (تهران):"),
            ("utc_iso", "UTC ISO:"),
            ("unix_s", "Unix (ثانیه):"),
            ("unix_ms", "Unix (میلی‌ثانیه):"),
        ):
            rf = tk.Frame(res_box, bg="#111827")
            rf.pack(fill="x", pady=1)
            tk.Label(rf, text=title, font=(font_fa, 8), fg="#94A3B8", bg="#111827").pack(side="right")
            vl = tk.Label(rf, text="—", font=("Consolas", 8, "bold"), fg="#38BDF8", bg="#111827", cursor="hand2")
            vl.pack(side="left")
            vl.bind("<Button-1>", lambda e, lbl=vl: self._copy(lbl.cget("text"), "مقدار"))
            ts_labels[k] = vl

        def _convert_ts():
            try:
                out = parse_any_time_input(ts_entry.get())
                for k, vl in ts_labels.items():
                    vl.configure(text=out[k], fg="#38BDF8")
            except Exception as exc:
                ts_labels["jalali"].configure(text=f"خطا: {exc}", fg="#F87171")

        tk.Button(
            row,
            text="تبدیل",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            cursor="hand2",
            command=_convert_ts,
        ).pack(side="left")
        _convert_ts()

        # بخش تولید IDهای برنامه‌نویسی
        id_row = tk.Frame(parent, bg="#0F172A")
        id_row.pack(fill="x", pady=(0, 8))
        for label, fn in (("GUID کپی", generate_guid), ("ULID کپی", generate_ulid), ("NanoID کپی", generate_nanoid)):
            tk.Button(
                id_row,
                text=f"⚡ {label}",
                font=(font_fa, 8, "bold"),
                bg="#1E293B",
                fg="#C4B5FD",
                relief="flat",
                pady=4,
                cursor="hand2",
                command=lambda f=fn, l=label: self._copy(f(), l),
            ).pack(side="right", expand=True, fill="x", padx=2)

        # دیکدر آفلاین JWT
        tk.Label(
            parent,
            text="🔐 دیکدر آفلاین JWT (بررسی زمان انقضا به تاریخ شمسی):",
            font=(font_fa, 8, "bold"),
            fg="#FBBF24",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(4, 4))
        jwt_row = tk.Frame(parent, bg="#0F172A")
        jwt_row.pack(fill="x", pady=(0, 4))
        jwt_entry = tk.Entry(jwt_row, font=("Consolas", 8), bg="#1E293B", fg="#F8FAFC", insertbackground="#FBBF24", relief="flat")
        jwt_entry.pack(side="right", fill="x", expand=True, ipady=4, padx=(6, 0))

        jwt_status = tk.Label(parent, text="توکن JWT را وارد کنید...", font=(font_fa, 8, "bold"), fg="#94A3B8", bg="#111827", pady=4)
        jwt_status.pack(fill="x", pady=(0, 4))

        jwt_frame = tk.Frame(parent, bg="#111827")
        jwt_frame.pack(fill="both", expand=True)
        jwt_scroll = tk.Scrollbar(jwt_frame, orient="vertical")
        jwt_out = tk.Text(
            jwt_frame,
            height=7,
            font=("Consolas", 8),
            wrap="word",
            yscrollcommand=jwt_scroll.set,
            bg="#111827",
            fg="#E2E8F0",
            bd=0,
            relief="flat",
        )
        jwt_scroll.config(command=jwt_out.yview)
        jwt_scroll.pack(side="left", fill="y")
        jwt_out.pack(side="right", fill="both", expand=True)

        def _decode_jwt():
            try:
                d = decode_jwt_offline(jwt_entry.get())
                jwt_status.configure(
                    text=f"{d['exp_status']}  |  exp: {d['exp_jalali']}  |  iat: {d['iat_jalali']}",
                    fg="#F87171" if d["is_expired"] else "#34D399",
                )
                jwt_out.delete("1.0", tk.END)
                jwt_out.insert("1.0", json.dumps(d["payload"], ensure_ascii=False, indent=2))
            except Exception as exc:
                jwt_status.configure(text=f"خطا: {exc}", fg="#F87171")

        tk.Button(
            jwt_row,
            text="بررسی JWT",
            font=(font_fa, 8, "bold"),
            bg="#D97706",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            cursor="hand2",
            command=_decode_jwt,
        ).pack(side="left")

    # ── تب ۲: دستیار Cron ──
    def _build_tab_cron(self, parent: tk.Frame, font_fa: str):
        tk.Label(
            parent,
            text="عبارت ۵ بخشی Cron (دقیقه ساعت روز ماه روزهفته):",
            font=(font_fa, 8, "bold"),
            fg="#E2E8F0",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 4))

        top = tk.Frame(parent, bg="#0F172A")
        top.pack(fill="x", pady=(0, 6))
        cron_entry = tk.Entry(top, font=("Consolas", 10, "bold"), bg="#1E293B", fg="#38BDF8", insertbackground="#38BDF8", relief="flat")
        cron_entry.pack(side="right", fill="x", expand=True, ipady=4, padx=(6, 0))
        cron_entry.insert(0, "*/15 9-17 * * 1-5")

        tz_var = tk.StringVar(value="tehran")
        desc_lbl = tk.Label(parent, text="", font=(font_fa, 9, "bold"), fg="#A7F3D0", bg="#111827", pady=6, wraplength=580)
        desc_lbl.pack(fill="x", pady=(0, 6))

        runs_frame = tk.Frame(parent, bg="#111827", highlightbackground="#1F2937", highlightthickness=1)
        runs_frame.pack(fill="both", expand=True, pady=(0, 8))
        runs_scroll = tk.Scrollbar(runs_frame, orient="vertical")
        runs_box = tk.Listbox(
            runs_frame,
            height=7,
            font=("Consolas", 9),
            yscrollcommand=runs_scroll.set,
            bg="#111827",
            fg="#E2E8F0",
            bd=0,
            highlightthickness=0,
        )
        runs_scroll.config(command=runs_box.yview)
        runs_scroll.pack(side="left", fill="y")
        runs_box.pack(side="right", fill="both", expand=True)

        def _analyze_cron():
            expr = cron_entry.get().strip()
            desc_lbl.configure(text=describe_cron_fa(expr))
            runs_box.delete(0, tk.END)
            try:
                runs = next_cron_runs(expr, count=5, tz_mode=tz_var.get())
                if not runs:
                    runs_box.insert(tk.END, "در ۳۶۶ روز آینده اجرایی یافت نشد")
                for idx, r in enumerate(runs, 1):
                    runs_box.insert(tk.END, f"{idx}. تهران: {r['tehran']}   |   {r['utc']}")
            except Exception as exc:
                runs_box.insert(tk.END, f"خطا: {exc}")

        tk.Button(
            top,
            text="تحلیل و پیش‌بینی",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            cursor="hand2",
            command=_analyze_cron,
        ).pack(side="left")

        tz_row = tk.Frame(parent, bg="#0F172A")
        tz_row.pack(fill="x", pady=(0, 6))
        for val, lbl in (("tehran", "محاسبه بر اساس ساعت تهران"), ("utc", "محاسبه بر اساس UTC")):
            tk.Radiobutton(
                tz_row,
                text=lbl,
                variable=tz_var,
                value=val,
                command=_analyze_cron,
                font=(font_fa, 8),
                fg="#CBD5E1",
                bg="#0F172A",
                selectcolor="#1E293B",
                activebackground="#0F172A",
            ).pack(side="right", padx=6)

        tk.Button(
            tz_row,
            text="📋 کپی Cron",
            font=(font_fa, 8, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            cursor="hand2",
            command=lambda: self._copy(cron_entry.get().strip(), "عبارت Cron"),
        ).pack(side="left")

        pre_frame = tk.Frame(parent, bg="#0F172A")
        pre_frame.pack(fill="x")
        for title, expr in CRON_PRESETS:
            def _pick(ex=expr):
                cron_entry.delete(0, tk.END)
                cron_entry.insert(0, ex)
                _analyze_cron()
            tk.Button(
                pre_frame,
                text=title,
                font=(font_fa, 7, "bold"),
                bg="#1E293B",
                fg="#CBD5E1",
                relief="flat",
                padx=5,
                pady=3,
                cursor="hand2",
                command=_pick,
            ).pack(side="right", padx=2, pady=2)

        _analyze_cron()

    # ── تب ۳: برنامه‌ریز جلسات ──
    def _build_tab_meetings(self, parent: tk.Frame, font_fa: str):
        tk.Label(
            parent,
            text="انتخاب ساعت جلسه به وقت تهران برای مشاهده معادل آن در شهرهای تیم:",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 8))

        ctrl = tk.Frame(parent, bg="#0F172A")
        ctrl.pack(fill="x", pady=(0, 10))
        now_teh = datetime.now(TEHRAN_TZ)
        h_var = tk.StringVar(value=f"{now_teh.hour:02d}")
        m_var = tk.StringVar(value="00")

        tk.Label(ctrl, text="ساعت تهران:", font=(font_fa, 9), fg="#94A3B8", bg="#0F172A").pack(side="right", padx=(0, 6))
        sp_h = tk.Spinbox(ctrl, from_=0, to=23, textvariable=h_var, width=4, font=("Consolas", 10, "bold"), bg="#1E293B", fg="#F8FAFC", relief="flat")
        sp_h.pack(side="right", padx=2)
        tk.Label(ctrl, text=":", font=("Consolas", 10, "bold"), fg="#F8FAFC", bg="#0F172A").pack(side="right")
        sp_m = tk.Spinbox(ctrl, from_=0, to=59, increment=15, textvariable=m_var, width=4, font=("Consolas", 10, "bold"), bg="#1E293B", fg="#F8FAFC", relief="flat")
        sp_m.pack(side="right", padx=2)

        list_frame = tk.Frame(parent, bg="#111827", highlightbackground="#1F2937", highlightthickness=1, padx=10, pady=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        row_labels: list[tuple[tk.Label, tk.Label]] = []
        for _ in range(7):
            rf = tk.Frame(list_frame, bg="#111827")
            rf.pack(fill="x", pady=4)
            c_lbl = tk.Label(rf, text="", font=(font_fa, 9, "bold"), fg="#CBD5E1", bg="#111827", anchor="e")
            c_lbl.pack(side="right")
            t_lbl = tk.Label(rf, text="", font=("Consolas", 10, "bold"), fg="#38BDF8", bg="#111827", anchor="w")
            t_lbl.pack(side="left")
            row_labels.append((c_lbl, t_lbl))

        last_rows: list[dict] = []

        def _update_meetings(*_):
            try:
                hh = int(h_var.get())
                mm = int(m_var.get())
            except Exception:
                return
            rows = convert_tehran_meeting_time(hh, mm)
            last_rows.clear()
            last_rows.extend(rows)
            for (c_lbl, t_lbl), item in zip(row_labels, rows):
                c_lbl.configure(text=item["city"])
                t_lbl.configure(text=f"{item['time']}  ({item['date']})")

        for b_text, cmd in (("محاسبه", _update_meetings),):
            tk.Button(ctrl, text=b_text, font=(font_fa, 8, "bold"), bg="#0284C7", fg="#FFFFFF", relief="flat", padx=10, cursor="hand2", command=cmd).pack(side="left", padx=4)

        def _copy_invite():
            lines = ["🕒 زمان جلسه پیشنهادی:"]
            for item in last_rows:
                lines.append(f"• {item['city']}: {item['time']} ({item['date']})")
            self._copy("\n".join(lines), "متن دعوت‌نامه جلسه")

        tk.Button(
            parent,
            text="📋 کپی متن آماده دعوت‌نامه جلسه",
            font=(font_fa, 9, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=_copy_invite,
        ).pack(fill="x")
        _update_meetings()

    # ── تب ۴: پومودورو و زمان‌بند اکشن سر ساعت ──
    def _build_tab_pomodoro_actions(self, parent: tk.Frame, font_fa: str):
        tk.Label(
            parent,
            text="⏱ تایمر تمرکز (Deep Work / پومودورو):",
            font=(font_fa, 9, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 6))

        p_row = tk.Frame(parent, bg="#0F172A")
        p_row.pack(fill="x", pady=(0, 12))
        for mins, lbl, bgc in (
            (25, "۲۵ دقیقه کار", "#059669"),
            (5, "۵ دقیقه استراحت", "#0284C7"),
            (45, "۴۵ دقیقه عمیق", "#7C3AED"),
        ):
            tk.Button(
                p_row,
                text=lbl,
                font=(font_fa, 8, "bold"),
                bg=bgc,
                fg="#FFFFFF",
                relief="flat",
                pady=5,
                cursor="hand2",
                command=lambda m=mins, l=lbl: self.app.start_pomodoro_timer(m, l),
            ).pack(side="right", expand=True, fill="x", padx=2)
        tk.Button(
            p_row,
            text="توقف",
            font=(font_fa, 8, "bold"),
            bg="#991B1B",
            fg="#FFFFFF",
            relief="flat",
            pady=5,
            cursor="hand2",
            command=self.app.stop_pomodoro_timer,
        ).pack(side="right", padx=2)

        tk.Frame(parent, bg="#1E293B", height=1).pack(fill="x", pady=(0, 10))

        tk.Label(
            parent,
            text="⚡ زمان‌بند اکشن سر ساعت (باز کردن لینک، Webhook یا اجرای دستور):",
            font=(font_fa, 9, "bold"),
            fg="#FBBF24",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 6))

        form = tk.Frame(parent, bg="#111827", highlightbackground="#1F2937", highlightthickness=1, padx=10, pady=8)
        form.pack(fill="x", pady=(0, 8))

        def _mk_row(lbl_txt: str):
            f = tk.Frame(form, bg="#111827")
            f.pack(fill="x", pady=3)
            tk.Label(f, text=lbl_txt, font=(font_fa, 8), fg="#94A3B8", bg="#111827", width=15, anchor="e").pack(side="right")
            e = tk.Entry(f, font=("Consolas", 9), bg="#1E293B", fg="#F8FAFC", insertbackground="#38BDF8", relief="flat")
            e.pack(side="right", fill="x", expand=True, ipady=3, padx=(0, 6))
            return e

        e_title = _mk_row("عنوان:")
        e_title.insert(0, "اجرای خودکار")
        e_mins = _mk_row("چند دقیقه دیگر:")
        e_mins.insert(0, "10")

        type_var = tk.StringVar(value="url")
        tf = tk.Frame(form, bg="#111827")
        tf.pack(fill="x", pady=3)
        tk.Label(tf, text="نوع اکشن:", font=(font_fa, 8), fg="#94A3B8", bg="#111827", width=15, anchor="e").pack(side="right")
        for val, lbl in (("url", "باز کردن لینک"), ("webhook", "POST Webhook"), ("command", "دستور سیستم")):
            tk.Radiobutton(
                tf,
                text=lbl,
                variable=type_var,
                value=val,
                font=(font_fa, 8),
                fg="#CBD5E1",
                bg="#111827",
                selectcolor="#1E293B",
                activebackground="#111827",
            ).pack(side="right", padx=4)

        e_target = _mk_row("لینک / دستور:")
        e_target.insert(0, "https://")

        def _schedule_action():
            try:
                mins = max(1, int(e_mins.get().strip()))
            except Exception:
                mins = 5
            target_dt = datetime.now(TEHRAN_TZ) + timedelta(minutes=mins)
            jy, jm, jd = gregorian_to_jalali(target_dt.year, target_dt.month, target_dt.day)
            j_date = f"{jy:04d}/{jm:02d}/{jd:02d}"
            self.app.alarm_store.add_alarm(
                title=e_title.get().strip() or "اکشن زمان‌بندی‌شده",
                hour=target_dt.hour,
                minute=target_dt.minute,
                repeat="once",
                dates=[j_date],
                play_sound=True,
                message=f"اکشن {type_var.get()}: {e_target.get().strip()}",
                action_type=type_var.get(),
                action_target=e_target.get().strip(),
            )
            self.app._refresh_display()
            self.app._show_toast(f"✓ اکشن برای {target_dt.strftime('%H:%M')} ثبت شد")

        tk.Button(
            parent,
            text="✓ ثبت اکشن زمان‌بندی‌شده",
            font=(font_fa, 9, "bold"),
            bg="#D97706",
            fg="#FFFFFF",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=_schedule_action,
        ).pack(fill="x")

    # ── تب ۵: سرور محلی AI (HTTP REST + MCP) ──
    def _build_tab_ai_mcp(self, parent: tk.Frame, font_fa: str):
        api = getattr(self.app, "local_api", None)
        port_var = tk.StringVar(value=str(int(self.app.config.get("ai_api_port", 17845))))
        is_on = bool(api and api.running)

        def _cur_port() -> int:
            try:
                p = int(port_var.get().strip())
                return p if 1024 <= p <= 65535 else 17845
            except Exception:
                return 17845

        tk.Label(
            parent,
            text="درگاه امن و محلی AI (فقط روی 127.0.0.1 — بدون ارسال داده به اینترنت) برای اتصال Claude، Antigravity، Cursor و اسکریپت‌ها:",
            font=(font_fa, 8),
            fg="#CBD5E1",
            bg="#0F172A",
            anchor="e",
            justify="right",
            wraplength=585,
        ).pack(fill="x", pady=(0, 6))

        st_lbl = tk.Label(
            parent,
            text=f"🟢 سرور محلی AI فعال است: http://127.0.0.1:{_cur_port()}  (۱۰ ابزار MCP آماده)" if is_on else "🔴 سرور محلی AI متوقف است",
            font=(font_fa, 9, "bold"),
            fg="#6EE7B7" if is_on else "#FCA5A5",
            bg="#064E3B" if is_on else "#450A0A",
            pady=6,
        )
        st_lbl.pack(fill="x", pady=(0, 6))

        def _update_status():
            now_on = bool(api and api.running)
            p = _cur_port()
            if now_on:
                st_lbl.configure(
                    text=f"🟢 سرور محلی AI فعال است: http://127.0.0.1:{p}  (۱۰ ابزار MCP آماده)",
                    fg="#6EE7B7",
                    bg="#064E3B",
                )
            else:
                err = getattr(api, "last_error", "") if api else ""
                st_lbl.configure(
                    text=f"🔴 سرور متوقف است{(' — ' + err) if err else ''}",
                    fg="#FCA5A5",
                    bg="#450A0A",
                )

        def _toggle_srv():
            if not api:
                return
            p = _cur_port()
            self.app.config["ai_api_port"] = p
            if api.running:
                api.stop()
                self.app.config["ai_api_enabled"] = False
            else:
                api.start(port=p)
                self.app.config["ai_api_enabled"] = True
            self.app._save_config()
            _update_status()
            _render_view(active_view["name"])

        def _apply_port():
            p = _cur_port()
            port_var.set(str(p))
            self.app.config["ai_api_port"] = p
            self.app._save_config()
            if api and api.running:
                api.stop()
                api.start(port=p)
            _update_status()
            _render_view(active_view["name"])
            self.app._show_toast(f"✓ پورت سرور روی {p} تنظیم شد")

        def _test_health():
            p = _cur_port()
            try:
                t0 = time.perf_counter()
                with urllib.request.urlopen(f"http://127.0.0.1:{p}/health", timeout=2.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                ms = int((time.perf_counter() - t0) * 1000)
                if data.get("ok"):
                    self.app._show_toast(f"✓ پاسخ سالم از سرور ({ms}ms | {data.get('tools_count', 10)} ابزار)")
                    _render_view("logs")
                else:
                    self.app._show_toast("⚠ پاسخ نامعتبر از سرور")
            except Exception as exc:
                self.app._show_toast(f"✕ خطا در اتصال: {exc}")

        ctrl_row = tk.Frame(parent, bg="#0F172A")
        ctrl_row.pack(fill="x", pady=(0, 6))
        tk.Button(
            ctrl_row,
            text="🔌 روشن / خاموش",
            font=(font_fa, 8, "bold"),
            bg="#1E293B",
            fg="#38BDF8",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=_toggle_srv,
        ).pack(side="right")
        tk.Button(
            ctrl_row,
            text="🧪 تست زنده /health",
            font=(font_fa, 8, "bold"),
            bg="#065F46",
            fg="#A7F3D0",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=_test_health,
        ).pack(side="right", padx=(0, 6))

        tk.Button(
            ctrl_row,
            text="اعمال پورت",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
            command=_apply_port,
        ).pack(side="left")
        tk.Entry(
            ctrl_row,
            textvariable=port_var,
            width=7,
            font=("Consolas", 9, "bold"),
            bg="#1E293B",
            fg="#FDE68A",
            insertbackground="#FDE68A",
            justify="center",
            relief="flat",
        ).pack(side="left", ipady=3, padx=(0, 6))
        tk.Label(ctrl_row, text="پورت:", font=(font_fa, 8), fg="#94A3B8", bg="#0F172A").pack(side="left")

        def _mcp_snippet() -> str:
            return json.dumps(
                {"mcpServers": {"persian-clock-widget": {"url": f"http://127.0.0.1:{_cur_port()}/mcp"}}},
                indent=2,
            )

        def _curl_snippet() -> str:
            p = _cur_port()
            return (
                f'curl -X POST http://127.0.0.1:{p}/alarms -H "Content-Type: application/json" '
                f'-d \'{{"title": "بررسی سرور", "in_minutes": 15}}\''
            )

        # نوار تغییر نمای داخلی تب AI
        sub_row = tk.Frame(parent, bg="#0F172A")
        sub_row.pack(fill="x", pady=(0, 6))
        active_view = {"name": "api"}
        sub_btns: dict[str, tk.Button] = {}

        # دکمه‌های پایین (همیشه چسبیده به پایین)
        btn_row = tk.Frame(parent, bg="#0F172A")
        btn_row.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Button(
            btn_row,
            text="📋 کپی کانفیگ MCP (Claude / Antigravity / Cursor)",
            font=(font_fa, 8, "bold"),
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=lambda: self._copy(_mcp_snippet(), "کانفیگ MCP"),
        ).pack(side="right", fill="x", expand=True, padx=(4, 0))
        tk.Button(
            btn_row,
            text="📋 کپی cURL تست",
            font=(font_fa, 8, "bold"),
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            pady=6,
            padx=8,
            cursor="hand2",
            command=lambda: self._copy(_curl_snippet(), "دستور cURL"),
        ).pack(side="left", padx=(0, 4))
        tk.Button(
            btn_row,
            text="📋 کپی URL",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            pady=6,
            padx=8,
            cursor="hand2",
            command=lambda: self._copy(f"http://127.0.0.1:{_cur_port()}", "آدرس REST API"),
        ).pack(side="left", padx=(0, 4))

        txt_frame = tk.Frame(parent, bg="#111827", highlightbackground="#1F2937", highlightthickness=1)
        txt_frame.pack(fill="both", expand=True)
        txt_scroll = tk.Scrollbar(txt_frame, orient="vertical")
        info_txt = tk.Text(
            txt_frame,
            yscrollcommand=txt_scroll.set,
            font=("Consolas", 9),
            wrap="word",
            bg="#111827",
            fg="#E2E8F0",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=8,
            cursor="arrow",
        )
        txt_scroll.config(command=info_txt.yview)
        txt_scroll.pack(side="left", fill="y")
        info_txt.pack(side="right", fill="both", expand=True)

        info_txt.tag_configure("hdr", foreground="#38BDF8", font=("Consolas", 9, "bold"))
        info_txt.tag_configure("ep", foreground="#34D399", font=("Consolas", 9, "bold"))
        info_txt.tag_configure("desc", foreground="#CBD5E1", font=(font_fa, 8))
        info_txt.tag_configure("code", foreground="#FDE68A", font=("Consolas", 9))
        info_txt.tag_configure("err", foreground="#FCA5A5", font=("Consolas", 9))

        def _render_view(name: str):
            active_view["name"] = name
            for k, b in sub_btns.items():
                b.configure(
                    bg="#0284C7" if k == name else "#1E293B",
                    fg="#FFFFFF" if k == name else "#CBD5E1",
                )
            p = _cur_port()
            info_txt.configure(state="normal")
            info_txt.delete("1.0", tk.END)

            if name == "api":
                info_txt.insert(tk.END, f"REST Endpoints (http://127.0.0.1:{p}):\n", "hdr")
                endpoints = [
                    ("GET  /health        ", "وضعیت سرور، پورت و آپتایم\n"),
                    ("GET  /now           ", "ساعت تهران، تاریخ شمسی، UTC، Unix و تعطیلی\n"),
                    ("GET  /ip            ", "IP فعلی، شهر/کشور، وضعیت قفل و تاریخچه ۳ روزه\n"),
                    ("GET  /alarms        ", "لیست آلارم‌ها و رویدادهای ثبت‌شده\n"),
                    ("GET  /dev/ids       ", "تولید UUID v4، ULID و NanoID\n"),
                    ("GET  /logs          ", "آخرین درخواست‌های دریافت‌شده\n"),
                    ("POST /convert       ", "تبدیل تاریخ شمسی / میلادی / Unix / ISO\n"),
                    ("POST /ip/lock       ", "فعال/غیرفعال کردن قفل شهر/IP\n"),
                    ("POST /alarms        ", "ثبت یادآور یا اکشن (in_minutes یا jalali_date)\n"),
                    ("POST /alarms/delete ", "حذف آلارم با شناسه (id)\n"),
                    ("POST /timer         ", "شروع تایمر پومودورو (minutes, label)\n"),
                    ("POST /timer/stop    ", "توقف تایمر پومودورو\n"),
                    ("POST /mcp           ", "درگاه MCP JSON-RPC 2.0\n\n"),
                ]
                for ep, desc in endpoints:
                    info_txt.insert(tk.END, f"  {ep} -> ", "ep")
                    info_txt.insert(tk.END, desc, "desc")

                info_txt.insert(tk.END, "ابزارهای آماده MCP (۱۰ ابزار برای هوش مصنوعی):\n", "hdr")
                mcp_list = [
                    "get_persian_datetime",
                    "convert_datetime",
                    "get_ip_location_status",
                    "toggle_ip_lock",
                    "list_alarms",
                    "schedule_reminder",
                    "delete_alarm",
                    "start_pomodoro_timer",
                    "stop_pomodoro_timer",
                    "generate_dev_ids",
                ]
                info_txt.insert(tk.END, "  • " + "\n  • ".join(mcp_list), "code")

            elif name == "clients":
                info_txt.insert(tk.END, "1) MCP Config (Claude Desktop / Antigravity / Cursor):\n", "hdr")
                info_txt.insert(tk.END, _mcp_snippet() + "\n\n", "code")
                info_txt.insert(tk.END, "2) نمونه cURL برای ثبت یادآور خودکار:\n", "hdr")
                info_txt.insert(tk.END, _curl_snippet() + "\n\n", "code")
                info_txt.insert(tk.END, "3) نمونه پایتون (تبدیل زمان با API محلی):\n", "hdr")
                py_sample = (
                    "import urllib.request, json\n"
                    f"req = urllib.request.Request('http://127.0.0.1:{p}/convert',\n"
                    "  data=json.dumps({'value': '1405/08/24 14:30'}).encode(),\n"
                    "  headers={'Content-Type': 'application/json'})\n"
                    "print(urllib.request.urlopen(req).read().decode())"
                )
                info_txt.insert(tk.END, py_sample, "code")

            elif name == "logs":
                info_txt.insert(tk.END, "📜 لاگ زنده درخواست‌های AI و API (۳۰ مورد اخیر):\n\n", "hdr")
                logs = api.get_logs() if api else []
                if not logs:
                    info_txt.insert(tk.END, "هنوز درخواستی ثبت نشده است. دکمه «🧪 تست زنده /health» را بزنید.", "desc")
                else:
                    for item in logs:
                        tag = "err" if int(item.get("status", 200)) >= 400 else "ep"
                        det = f"  ({item['detail']})" if item.get("detail") else ""
                        info_txt.insert(
                            tk.END,
                            f"[{item['time']}] {item['method']:<4} {item['path']:<15} -> {item['status']}{det}\n",
                            tag,
                        )

            info_txt.configure(state="disabled")

        for key, label in [
            ("api", "📡 ابزارها و REST API"),
            ("clients", "🔌 کانفیگ کلاینت‌ها"),
            ("logs", "📜 لاگ زنده AI"),
        ]:
            b = tk.Button(
                sub_row,
                text=label,
                font=(font_fa, 8, "bold"),
                relief="flat",
                padx=8,
                pady=4,
                cursor="hand2",
                command=lambda k=key: _render_view(k),
            )
            b.pack(side="right", padx=(4, 0))
            sub_btns[key] = b

        _render_view("api")
