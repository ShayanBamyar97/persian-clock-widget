# -*- coding: utf-8 -*-
"""
همگام‌سازی تقویم گوگل (Google Calendar) و تبدیل خودکار جلسات به ریمایندر ویجت
پشتیبانی از هر دو روش:
  1. لینک خصوصی iCal (.ics) تقویم گوگل (بدون نیاز به هیچ تنظیمات کلود)
  2. اتصال مستقیم با اکانت گوگل از طریق OAuth 2.0 Desktop (دریافت توکن و Refresh خودکار)
"""

from datetime import datetime, timedelta, timezone
import http.server
import json
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    from src.calendar_data import TEHRAN_TZ, gregorian_to_jalali
    from src.win_utils import get_resource_path
except ImportError:
    from calendar_data import TEHRAN_TZ, gregorian_to_jalali
    from win_utils import get_resource_path


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
GOOGLE_EVENTS_API = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def _parse_tz(tzid: str | None):
    if not tzid:
        return TEHRAN_TZ
    tzid = tzid.strip().strip('"')
    if tzid.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    if tzid in ("Asia/Tehran", "Iran Standard Time"):
        return TEHRAN_TZ
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tzid)
        except Exception:
            pass
    return TEHRAN_TZ


def _parse_ics_datetime(val: str, tzid: str | None = None) -> tuple[datetime | None, bool]:
    """تبدیل تاریخ/ساعت iCal به datetime و تشخیص رویداد تمام‌روز"""
    s = val.strip()
    if not s:
        return None, False
    # All-day: YYYYMMDD
    if re.fullmatch(r"\d{8}", s):
        dt = datetime.strptime(s, "%Y%m%d").replace(tzinfo=TEHRAN_TZ)
        return dt, True
    # UTC: YYYYMMDDTHHMMSSZ
    if s.endswith("Z"):
        try:
            dt = datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return dt.astimezone(TEHRAN_TZ), False
        except ValueError:
            return None, False
    # Local / TZID: YYYYMMDDTHHMMSS
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=_parse_tz(tzid)).astimezone(TEHRAN_TZ), False
        except ValueError:
            continue
    return None, False


def _unfold_ics_lines(raw_text: str) -> list[str]:
    """باز کردن خطوط شکسته RFC 5545"""
    raw_lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _unescape_ics_text(text: str) -> str:
    return (
        text.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _extract_meeting_url(text: str) -> str:
    m = re.search(r"https?://(?:meet\.google\.com|[\w.-]*zoom\.us|teams\.microsoft\.com)/[^\s<>\"']+", text)
    if m:
        return m.group(0)
    m2 = re.search(r"https?://[^\s<>\"']+", text)
    return m2.group(0) if m2 else ""


def parse_ics_events(raw_ics: str, days_ahead: int = 7) -> list[dict]:
    """پارس رویدادهای تقویم گوگل از فایل/لینک iCal برای امروز تا N روز آینده"""
    now_teh = datetime.now(TEHRAN_TZ)
    win_start = now_teh.replace(hour=0, minute=0, second=0, microsecond=0)
    win_end = win_start + timedelta(days=days_ahead + 1)

    lines = _unfold_ics_lines(raw_ics)
    events: list[dict] = []
    in_event = False
    cur: dict = {}

    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            cur = {}
            continue
        if line == "END:VEVENT":
            if in_event and cur.get("dtstart"):
                start_dt: datetime = cur["dtstart"]
                end_dt: datetime = cur.get("dtend") or (start_dt + timedelta(hours=1))
                rrule = cur.get("rrule", "")

                occurrences: list[tuple[datetime, datetime]] = []
                if "FREQ=DAILY" in rrule:
                    step = timedelta(days=1)
                    occ_s, occ_e = start_dt, end_dt
                    while occ_s < win_end:
                        if occ_s >= win_start:
                            occurrences.append((occ_s, occ_e))
                        occ_s += step
                        occ_e += step
                elif "FREQ=WEEKLY" in rrule:
                    step = timedelta(days=7)
                    occ_s, occ_e = start_dt, end_dt
                    while occ_s < win_end:
                        if occ_s >= win_start:
                            occurrences.append((occ_s, occ_e))
                        occ_s += step
                        occ_e += step
                else:
                    if win_start <= start_dt < win_end:
                        occurrences.append((start_dt, end_dt))

                summary = cur.get("summary") or "جلسه Google Calendar"
                desc = cur.get("description") or ""
                loc = cur.get("location") or ""
                meet_url = _extract_meeting_url(f"{loc}\n{desc}")
                uid = cur.get("uid") or str(uuid.uuid4())[:8]

                for idx, (occ_s, occ_e) in enumerate(occurrences):
                    events.append(
                        {
                            "id": f"{uid}_{idx}",
                            "summary": summary,
                            "start": occ_s,
                            "end": occ_e,
                            "all_day": bool(cur.get("all_day", False)),
                            "location": loc,
                            "description": desc,
                            "meet_url": meet_url,
                        }
                    )
            in_event = False
            cur = {}
            continue

        if not in_event or ":" not in line:
            continue

        prop_part, val = line.split(":", 1)
        prop_tokens = prop_part.split(";")
        prop_name = prop_tokens[0].upper()
        tzid = None
        for tok in prop_tokens[1:]:
            if tok.upper().startswith("TZID="):
                tzid = tok.split("=", 1)[1]

        if prop_name == "SUMMARY":
            cur["summary"] = _unescape_ics_text(val)
        elif prop_name == "DESCRIPTION":
            cur["description"] = _unescape_ics_text(val)
        elif prop_name == "LOCATION":
            cur["location"] = _unescape_ics_text(val)
        elif prop_name == "UID":
            cur["uid"] = val.strip()
        elif prop_name == "RRULE":
            cur["rrule"] = val.upper()
        elif prop_name == "DTSTART":
            dt, is_all_day = _parse_ics_datetime(val, tzid)
            if dt is not None:
                cur["dtstart"] = dt
                cur["all_day"] = is_all_day
        elif prop_name == "DTEND":
            dt, _ = _parse_ics_datetime(val, tzid)
            if dt is not None:
                cur["dtend"] = dt

    events.sort(key=lambda e: e["start"])
    return events


def fetch_ics_events(ics_url: str, days_ahead: int = 7) -> list[dict]:
    req = urllib.request.Request(
        ics_url.strip(),
        headers={"User-Agent": "PersianClockWidget/2.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return parse_ics_events(raw, days_ahead=days_ahead)


def run_google_oauth_flow(client_id: str, client_secret: str, token_path: str) -> dict:
    """انجام ورود OAuth 2.0 گوگل روی مرورگر و ذخیره access_token + refresh_token"""
    result_box: dict = {"code": None, "error": None}
    done_ev = threading.Event()

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                result_box["code"] = qs["code"][0]
                body = (
                    "<html><body style='font-family:sans-serif;text-align:center;padding:40px;'>"
                    "<h2>اتصال تقویم گوگل با موفقیت انجام شد!</h2>"
                    "<p>می‌توانید این تب را ببندید و به ویجت ساعت برگردید.</p>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
            else:
                result_box["error"] = qs.get("error", ["oauth_cancelled"])[0]
                body = b"<html><body><h3>Google OAuth failed or cancelled.</h3></body></html>"
                self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            done_ev.set()

        def log_message(self, format, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}"

    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()

    try:
        auth_params = urllib.parse.urlencode(
            {
                "client_id": client_id.strip(),
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": GOOGLE_CALENDAR_SCOPE,
                "access_type": "offline",
                "prompt": "select_account consent",
            }
        )
        webbrowser.open(f"{GOOGLE_AUTH_URL}?{auth_params}")
        if not done_ev.wait(timeout=180):
            raise TimeoutError("زمان انتظار برای ورود با اکانت گوگل به پایان رسید.")
    finally:
        server.shutdown()
        server.server_close()

    if result_box["error"]:
        raise RuntimeError(f"خطای ورود گوگل: {result_box['error']}")

    token_payload = urllib.parse.urlencode(
        {
            "code": result_box["code"],
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=token_payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))

    token_data["client_id"] = client_id.strip()
    token_data["client_secret"] = client_secret.strip()
    token_data["obtained_at"] = int(datetime.now(timezone.utc).timestamp())
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    return token_data


def _refresh_oauth_token_if_needed(token_path: str) -> dict:
    if not os.path.exists(token_path):
        raise FileNotFoundError("توکن گوگل یافت نشد. ابتدا وارد اکانت گوگل شوید.")
    with open(token_path, "r", encoding="utf-8") as f:
        token_data = json.load(f)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    obtained_at = int(token_data.get("obtained_at", 0))
    expires_in = int(token_data.get("expires_in", 3600))
    if now_ts < obtained_at + expires_in - 60:
        return token_data

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return token_data

    payload = urllib.parse.urlencode(
        {
            "client_id": token_data.get("client_id", ""),
            "client_secret": token_data.get("client_secret", ""),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        new_data = json.loads(resp.read().decode("utf-8"))

    token_data["access_token"] = new_data["access_token"]
    if "expires_in" in new_data:
        token_data["expires_in"] = new_data["expires_in"]
    token_data["obtained_at"] = now_ts
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    return token_data


def fetch_oauth_events(token_path: str, days_ahead: int = 7) -> list[dict]:
    token_data = _refresh_oauth_token_if_needed(token_path)
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise RuntimeError("Access token نامعتبر است.")

    now_teh = datetime.now(TEHRAN_TZ)
    win_start = now_teh.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    win_end = win_start + timedelta(days=days_ahead + 1)

    qs = urllib.parse.urlencode(
        {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeMax": win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "maxResults": "100",
        }
    )
    req = urllib.request.Request(
        f"{GOOGLE_EVENTS_API}?{qs}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    events: list[dict] = []
    for item in data.get("items", []):
        if item.get("status") == "cancelled":
            continue
        start_obj = item.get("start") or {}
        end_obj = item.get("end") or {}
        all_day = False
        if "dateTime" in start_obj:
            s_dt = datetime.fromisoformat(start_obj["dateTime"].replace("Z", "+00:00")).astimezone(TEHRAN_TZ)
            e_str = end_obj.get("dateTime")
            e_dt = (
                datetime.fromisoformat(e_str.replace("Z", "+00:00")).astimezone(TEHRAN_TZ)
                if e_str
                else s_dt + timedelta(hours=1)
            )
        elif "date" in start_obj:
            all_day = True
            s_dt = datetime.strptime(start_obj["date"], "%Y-%m-%d").replace(tzinfo=TEHRAN_TZ)
            e_dt = s_dt + timedelta(days=1)
        else:
            continue

        meet_url = item.get("hangoutLink") or _extract_meeting_url(
            f"{item.get('location', '')}\n{item.get('description', '')}"
        )
        events.append(
            {
                "id": item.get("id", str(uuid.uuid4())[:8]),
                "summary": item.get("summary") or "جلسه Google Calendar",
                "start": s_dt,
                "end": e_dt,
                "all_day": all_day,
                "location": item.get("location", ""),
                "description": item.get("description", ""),
                "meet_url": meet_url,
            }
        )
    events.sort(key=lambda e: e["start"])
    return events


def sync_google_events_to_alarm_store(events: list[dict], alarm_store, config: dict) -> int:
    """
    تبدیل جلسات گوگل به ریمایندر در AlarmStore:
      1) یادآوری N دقیقه قبل از هر جلسه (قابل تنظیم؛ پیش‌فرض ۱۰ دقیقه قبل)
      2) یادآوری خلاصه جلسات اول روز در ساعت دلخواه (مثلاً 09:00)
    """
    remind_before = bool(config.get("google_remind_before_enabled", True))
    mins_before = max(0, min(180, int(config.get("google_remind_minutes_before", 10))))
    morning_on = bool(config.get("google_morning_summary_enabled", True))
    morning_time_str = str(config.get("google_morning_summary_time", "09:00")).strip()
    sound_file = config.get("google_cal_sound") or config.get("default_alarm_sound", "alarm.mp3")

    m_parts = morning_time_str.split(":")
    try:
        m_hour = max(0, min(23, int(m_parts[0])))
        m_min = max(0, min(59, int(m_parts[1]))) if len(m_parts) > 1 else 0
    except Exception:
        m_hour, m_min = 9, 0

    # حفظ آلارم‌های شخصی کاربر و جایگزینی فقط ریمایندرهای قبلی گوگل
    alarm_store.alarms = [a for a in alarm_store.alarms if a.get("source") != "google_calendar"]
    added_count = 0

    muted_ids = set(config.get("google_cal_muted_ids") or [])
    deleted_ids = set(config.get("google_cal_deleted_ids") or [])

    by_day: dict[tuple[int, int, int], list[dict]] = {}
    for ev in events:
        ev_id = str(ev.get("id", ""))
        if ev_id in deleted_ids:
            continue
        s_dt: datetime = ev["start"]
        e_dt: datetime = ev["end"]
        jy, jm, jd = gregorian_to_jalali(s_dt.year, s_dt.month, s_dt.day)
        by_day.setdefault((jy, jm, jd), []).append(ev)

        if not remind_before or ev.get("all_day") or ev_id in muted_ids:
            continue

        rem_dt = s_dt - timedelta(minutes=mins_before)
        r_jy, r_jm, r_jd = gregorian_to_jalali(rem_dt.year, rem_dt.month, rem_dt.day)
        date_key = f"{r_jy:04d}/{r_jm:02d}/{r_jd:02d}"
        title = (
            f"📅 {ev['summary']} ({mins_before} دقیقه دیگر)"
            if mins_before > 0
            else f"📅 {ev['summary']}"
        )
        msg_lines = [f"زمان جلسه: {s_dt.strftime('%H:%M')} تا {e_dt.strftime('%H:%M')}"]
        if ev.get("location"):
            msg_lines.append(f"مکان: {ev['location']}")
        if ev.get("meet_url"):
            msg_lines.append(f"لینک: {ev['meet_url']}")

        alarm_store.alarms.append(
            {
                "id": f"gcal_{uuid.uuid4().hex[:8]}",
                "title": title,
                "message": "\n".join(msg_lines),
                "hour": rem_dt.hour,
                "minute": rem_dt.minute,
                "repeat_mode": "once",
                "dates": [date_key],
                "jy": r_jy,
                "jm": r_jm,
                "jd": r_jd,
                "enabled": True,
                "play_sound": True,
                "show_popup": True,
                "sound_file": sound_file,
                "action_type": "none",
                "action_target": "",
                "source": "google_calendar",
                "google_event_id": ev.get("id", ""),
            }
        )
        added_count += 1

    if morning_on:
        for (jy, jm, jd), day_events in sorted(by_day.items()):
            date_key = f"{jy:04d}/{jm:02d}/{jd:02d}"
            lines = []
            for ev in day_events[:10]:
                t_lbl = "تمام‌روز" if ev.get("all_day") else ev["start"].strftime("%H:%M")
                lines.append(f"• {t_lbl} — {ev['summary']}")
            alarm_store.alarms.append(
                {
                    "id": f"gcal_day_{uuid.uuid4().hex[:8]}",
                    "title": f"☀️ برنامه جلسات امروز ({len(day_events)} جلسه)",
                    "message": "\n".join(lines),
                    "hour": m_hour,
                    "minute": m_min,
                    "repeat_mode": "once",
                    "dates": [date_key],
                    "jy": jy,
                    "jm": jm,
                    "jd": jd,
                    "enabled": True,
                    "play_sound": True,
                    "show_popup": True,
                    "sound_file": sound_file,
                    "action_type": "none",
                    "action_target": "",
                    "source": "google_calendar",
                }
            )
            added_count += 1

    alarm_store.save()
    return added_count


class GoogleCalendarWindow:
    """پنجره اتصال به تقویم گوگل و تنظیم ریمایندر خودکار جلسات"""

    def __init__(self, app):
        self.app = app
        self.win: tk.Toplevel | None = None
        self.preview_win: tk.Toplevel | None = None
        self._thumb_photo = None
        self._full_photo = None

    def _open_guide_preview(self):
        img_path = get_resource_path(os.path.join("assets", "images", "gcal_guide.png"))
        if not os.path.exists(img_path) or Image is None or ImageTk is None:
            messagebox.showinfo("راهنما", "تصویر راهنما یافت نشد.", parent=self.win)
            return
        if self.preview_win and self.preview_win.winfo_exists():
            self.preview_win.deiconify()
            self.preview_win.lift()
            self.preview_win.focus_force()
            return

        pwin = tk.Toplevel(self.win or self.app.root)
        self.preview_win = pwin
        pwin.title("🖼️ راهنمای تصویری کپی لینک Secret address in iCal format")
        pwin.configure(bg="#0F172A")
        pwin.attributes("-topmost", True)

        pil_img = Image.open(img_path)
        max_w = max(640, min(1100, pwin.winfo_screenwidth() - 100))
        max_h = max(400, min(720, pwin.winfo_screenheight() - 140))
        pil_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        self._full_photo = ImageTk.PhotoImage(pil_img)

        pw = pil_img.width + 24
        ph = pil_img.height + 64
        px = (pwin.winfo_screenwidth() - pw) // 2
        py = max(20, (pwin.winfo_screenheight() - ph) // 2)
        pwin.geometry(f"{pw}x{ph}+{px}+{py}")

        tk.Label(
            pwin,
            text="دقیقاً مطابق فلش قرمز، روی آیکون کپی کنار «Secret address in iCal format» کلیک کنید:",
            font=(self.app.config.get("font_family", "Vazir"), 9, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
            pady=6,
        ).pack(fill="x")

        lbl = tk.Label(pwin, image=self._full_photo, bg="#0F172A", cursor="hand2")
        lbl.pack(padx=12, pady=(0, 8))
        lbl.bind("<Button-1>", lambda e: pwin.destroy())

        tk.Button(
            pwin,
            text="بستن",
            font=(self.app.config.get("font_family", "Vazir"), 9),
            bg="#334155",
            fg="#F8FAFC",
            padx=16,
            pady=3,
            relief="flat",
            command=pwin.destroy,
        ).pack(pady=(0, 8))

    def show(self):
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            return

        win = tk.Toplevel(self.app.root)
        self.win = win
        win.title("📅 اتصال به تقویم گوگل (Google Calendar Reminders)")
        win.configure(bg="#0F172A")
        win.attributes("-topmost", True)
        w = 620
        h = min(760, max(580, win.winfo_screenheight() - 80))
        sx = (win.winfo_screenwidth() - w) // 2
        sy = max(15, (win.winfo_screenheight() - h) // 2)
        win.geometry(f"{w}x{h}+{sx}+{sy}")

        font_fa = self.app.config.get("font_family", "Vazir")
        cfg = self.app.config

        main = tk.Frame(win, bg="#0F172A", padx=16, pady=14)
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="📅 همگام‌سازی جلسات Google Calendar با ریمایندر ویجت",
            font=(font_fa, 11, "bold"),
            fg="#38BDF8",
            bg="#0F172A",
            anchor="e",
        ).pack(fill="x", pady=(0, 8))

        status_var = tk.StringVar(
            value=cfg.get("google_cal_last_status") or "هنوز همگام‌سازی انجام نشده است."
        )
        tk.Label(
            main,
            textvariable=status_var,
            font=(font_fa, 8),
            fg="#A7F3D0",
            bg="#1E293B",
            padx=10,
            pady=6,
            anchor="e",
        ).pack(fill="x", pady=(0, 8))

        # ── اتصال ساده با ۲ کلیک (یا ورود OAuth اختیاری) ──
        conn_box = tk.LabelFrame(
            main,
            text="\u200f ۱. اتصال به تقویم گوگل (ساده و سریع) ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            padx=10,
            pady=8,
            labelanchor="ne",
        )
        conn_box.pack(fill="x", pady=(0, 8))

        mode_var = tk.StringVar(value=cfg.get("google_cal_mode", "ics"))
        ics_var = tk.StringVar(value=cfg.get("google_cal_ics_url", ""))
        cid_var = tk.StringVar(value=cfg.get("google_oauth_client_id", ""))
        csec_var = tk.StringVar(value=cfg.get("google_oauth_client_secret", ""))

        guide_wrap = tk.Frame(conn_box, bg="#1E293B")
        guide_wrap.pack(fill="x", pady=(0, 8))

        steps_frame = tk.Frame(guide_wrap, bg="#1E293B")
        steps_frame.pack(side="right", fill="both", expand=True)

        steps_data = (
            ("۱", "روی دکمه «باز کردن سایت تقویم گوگل» کلیک کنید و اکانت خود را انتخاب کنید."),
            ("۲", "از منوی سمت چپ روی اسم تقویم خود بزنید و به پایین صفحه اسکرول کنید."),
            ("۳", "در بخش Integrate calendar، لینک Secret address in iCal format را کپی کنید."),
            ("۴", "به همین پنجره برگردید و دکمه «پیست از کلیپ‌بورد و اتصال فوری» را بزنید."),
        )
        for num_txt, step_txt in steps_data:
            s_row = tk.Frame(steps_frame, bg="#1E293B")
            s_row.pack(fill="x", pady=1)
            tk.Label(
                s_row,
                text=num_txt,
                font=(font_fa, 8, "bold"),
                fg="#0F172A",
                bg="#38BDF8",
                width=2,
            ).pack(side="right", padx=(6, 0))
            tk.Label(
                s_row,
                text=f"\u200f{step_txt}",
                font=(font_fa, 8),
                fg="#CBD5E1",
                bg="#1E293B",
                justify="right",
                anchor="e",
            ).pack(side="right", fill="x", expand=True)

        # تصویر نمونه راهنما (با کلیک بزرگ می‌شود)
        guide_img_path = get_resource_path(os.path.join("assets", "images", "gcal_guide.png"))
        if os.path.exists(guide_img_path) and Image is not None and ImageTk is not None:
            try:
                thumb_pil = Image.open(guide_img_path)
                thumb_pil.thumbnail((155, 86), Image.Resampling.LANCZOS)
                self._thumb_photo = ImageTk.PhotoImage(thumb_pil)
                thumb_box = tk.Frame(guide_wrap, bg="#0F172A", highlightbackground="#38BDF8", highlightthickness=1)
                thumb_box.pack(side="left", padx=(0, 10), anchor="n")
                thumb_lbl = tk.Label(thumb_box, image=self._thumb_photo, bg="#0F172A", cursor="hand2")
                thumb_lbl.pack()
                thumb_cap = tk.Label(
                    thumb_box,
                    text="🔍 کلیک برای بزرگ‌نمایی",
                    font=(font_fa, 7, "bold"),
                    fg="#38BDF8",
                    bg="#0F172A",
                    cursor="hand2",
                    pady=2,
                )
                thumb_cap.pack(fill="x")
                thumb_lbl.bind("<Button-1>", lambda e: self._open_guide_preview())
                thumb_cap.bind("<Button-1>", lambda e: self._open_guide_preview())
            except Exception:
                pass

        quick_row = tk.Frame(conn_box, bg="#1E293B")
        quick_row.pack(fill="x", pady=(0, 6))

        def _open_google_calendar_web():
            webbrowser.open("https://calendar.google.com/calendar/r/settings")
            status_var.set("\u200f🌐 صفحه تنظیمات تقویم گوگل باز شد؛ اکانت را انتخاب و لینک iCal را کپی کنید.")

        def _paste_and_connect():
            try:
                clip = win.clipboard_get().strip()
            except Exception:
                clip = ""
            if not clip.startswith("http"):
                messagebox.showwarning(
                    "لینک در کلیپ‌بورد نیست",
                    "\u200fابتدا از تنظیمات Google Calendar لینک Secret address in iCal format را کپی کنید، سپس این دکمه را بزنید.",
                    parent=win,
                )
                return
            ics_var.set(clip)
            mode_var.set("ics")
            enabled_var.set(True)
            _sync_now()

        tk.Button(
            quick_row,
            text="مرحله ۱: باز کردن سایت تقویم گوگل 🌐",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=_open_google_calendar_web,
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            quick_row,
            text="مرحله ۲: پیست لینک از کلیپ‌بورد و اتصال فوری 📋",
            font=(font_fa, 8, "bold"),
            bg="#10B981",
            fg="#0F172A",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=_paste_and_connect,
        ).pack(side="right")

        tk.Entry(
            conn_box,
            textvariable=ics_var,
            font=("Consolas", 8),
            bg="#0F172A",
            fg="#94A3B8",
            insertbackground="#38BDF8",
        ).pack(fill="x", pady=(2, 6))

        # بخش پیشرفته OAuth (مخفی تا زمان کلیک کاربر)
        adv_frame = tk.Frame(conn_box, bg="#1E293B")
        adv_visible = {"on": False}

        def _toggle_adv():
            adv_visible["on"] = not adv_visible["on"]
            if adv_visible["on"]:
                adv_frame.pack(fill="x", pady=(4, 0))
                adv_toggle_btn.configure(text="▲ بستن تنظیمات پیشرفته OAuth")
            else:
                adv_frame.pack_forget()
                adv_toggle_btn.configure(text="⚙️ اتصال مستقیم با فایل credentials.json / OAuth (پیشرفته)")

        adv_toggle_btn = tk.Button(
            conn_box,
            text="⚙️ اتصال مستقیم با فایل credentials.json / OAuth (پیشرفته)",
            font=(font_fa, 8),
            bg="#0F172A",
            fg="#94A3B8",
            relief="flat",
            cursor="hand2",
            anchor="w",
            command=_toggle_adv,
        )
        adv_toggle_btn.pack(fill="x")

        oauth_row = tk.Frame(adv_frame, bg="#1E293B")
        oauth_row.pack(fill="x", pady=(4, 0))
        tk.Label(oauth_row, text="Client ID:", font=("Consolas", 8), fg="#94A3B8", bg="#1E293B").pack(side="left")
        tk.Entry(oauth_row, textvariable=cid_var, width=22, font=("Consolas", 8), bg="#0F172A", fg="#F8FAFC").pack(
            side="left", padx=(4, 8)
        )
        tk.Label(oauth_row, text="Secret:", font=("Consolas", 8), fg="#94A3B8", bg="#1E293B").pack(side="left")
        tk.Entry(oauth_row, textvariable=csec_var, width=16, show="*", font=("Consolas", 8), bg="#0F172A", fg="#F8FAFC").pack(
            side="left", padx=(4, 6)
        )

        def _load_creds_json():
            p = filedialog.askopenfilename(
                parent=win,
                title="انتخاب فایل credentials.json گوگل",
                filetypes=[("JSON files", "*.json")],
            )
            if not p:
                return
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                body = raw.get("installed") or raw.get("web") or raw
                cid_var.set(body.get("client_id", ""))
                csec_var.set(body.get("client_secret", ""))
                mode_var.set("oauth")
                status_var.set("✓ فایل credentials.json بارگذاری شد. دکمه «انتخاب اکانت گوگل» را بزنید.")
            except Exception as exc:
                messagebox.showerror("خطا", f"خواندن فایل ناموفق بود:\n{exc}", parent=win)

        def _connect_oauth():
            cid, csec = cid_var.get().strip(), csec_var.get().strip()
            if not cid or not csec:
                messagebox.showwarning("ناقص", "ابتدا فایل credentials.json را انتخاب کنید یا Client ID و Secret را وارد کنید.", parent=win)
                return
            mode_var.set("oauth")
            enabled_var.set(True)
            status_var.set("⏳ در حال باز کردن مرورگر برای انتخاب اکانت گوگل...")
            win.update_idletasks()

            def _worker():
                try:
                    run_google_oauth_flow(cid, csec, self.app.google_token_path)
                    win.after(0, lambda: status_var.set("✓ اتصال اکانت گوگل برقرار شد! در حال همگام‌سازی..."))
                    win.after(100, _sync_now)
                except Exception as exc:
                    win.after(0, lambda: status_var.set(f"❌ خطا در اتصال گوگل: {exc}"))

            threading.Thread(target=_worker, daemon=True).start()

        oauth_btns = tk.Frame(adv_frame, bg="#1E293B")
        oauth_btns.pack(fill="x", pady=(6, 0))
        tk.Button(
            oauth_btns,
            text="📂 انتخاب credentials.json",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            relief="flat",
            command=_load_creds_json,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            oauth_btns,
            text="🔐 انتخاب اکانت گوگل در مرورگر",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            command=_connect_oauth,
        ).pack(side="left")

        # ── تنظیمات یادآوری جلسات ──
        rem_box = tk.LabelFrame(
            main,
            text="\u200f ۲. تنظیمات زمان یادآوری جلسات ",
            font=(font_fa, 9, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            padx=10,
            pady=8,
            labelanchor="ne",
        )
        rem_box.pack(fill="x", pady=(0, 8))

        enabled_var = tk.BooleanVar(value=bool(cfg.get("google_cal_enabled", False)))
        before_on_var = tk.BooleanVar(value=bool(cfg.get("google_remind_before_enabled", True)))
        before_mins_var = tk.IntVar(value=int(cfg.get("google_remind_minutes_before", 10)))
        morning_on_var = tk.BooleanVar(value=bool(cfg.get("google_morning_summary_enabled", True)))
        morning_time_var = tk.StringVar(value=str(cfg.get("google_morning_summary_time", "09:00")))
        sync_mins_var = tk.IntVar(value=int(cfg.get("google_cal_sync_minutes", 15)))

        r0 = tk.Frame(rem_box, bg="#1E293B")
        r0.pack(fill="x", pady=(0, 3))
        tk.Checkbutton(
            r0,
            text="\u200f🔄 همگام‌سازی خودکار در پس‌زمینه",
            variable=enabled_var,
            font=(font_fa, 8, "bold"),
            fg="#F8FAFC",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(side="right")
        tk.Label(r0, text="\u200fهر", font=(font_fa, 8), fg="#94A3B8", bg="#1E293B").pack(
            side="right", padx=(6, 4)
        )
        tk.Spinbox(r0, from_=5, to=120, textvariable=sync_mins_var, width=4, font=("Consolas", 9)).pack(
            side="right", padx=(4, 0)
        )
        tk.Label(r0, text="\u200fدقیقه", font=(font_fa, 8), fg="#94A3B8", bg="#1E293B").pack(
            side="right", padx=(0, 4)
        )

        r1 = tk.Frame(rem_box, bg="#1E293B")
        r1.pack(fill="x", pady=(3, 3))
        tk.Checkbutton(
            r1,
            text="\u200f⏰ یادآوری قبل از شروع هر جلسه",
            variable=before_on_var,
            font=(font_fa, 8, "bold"),
            fg="#FBBF24",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(side="right")
        tk.Spinbox(r1, from_=0, to=180, textvariable=before_mins_var, width=5, font=("Consolas", 9)).pack(
            side="right", padx=6
        )
        tk.Label(r1, text="\u200fدقیقه قبل از جلسه", font=(font_fa, 8), fg="#CBD5E1", bg="#1E293B").pack(side="right")

        r2 = tk.Frame(rem_box, bg="#1E293B")
        r2.pack(fill="x", pady=(3, 0))
        tk.Checkbutton(
            r2,
            text="\u200f☀️ یادآوری خلاصه جلسات اول روز در ساعت",
            variable=morning_on_var,
            font=(font_fa, 8, "bold"),
            fg="#A7F3D0",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
        ).pack(side="right")
        tk.Entry(r2, textvariable=morning_time_var, width=7, font=("Consolas", 9), justify="center").pack(
            side="right", padx=6
        )
        tk.Label(r2, text="\u200f(مثال 09:00)", font=(font_fa, 8), fg="#94A3B8", bg="#1E293B").pack(
            side="right"
        )

        # ── پیش‌نمایش و مدیریت جلسات (انتخاب، بی‌صدا کردن آلارم، حذف) ──
        list_box = tk.LabelFrame(
            main,
            text="\u200f ۳. جلسات همگام‌سازی‌شده (برای تغییر آلارم دبل‌کلیک یا انتخاب کنید) ",
            font=(font_fa, 9, "bold"),
            fg="#E2E8F0",
            bg="#1E293B",
            padx=8,
            pady=6,
            labelanchor="ne",
        )
        list_box.pack(fill="both", expand=True, pady=(0, 8))

        ev_listbox = tk.Listbox(
            list_box,
            bg="#0F172A",
            fg="#E2E8F0",
            font=(font_fa, 8),
            selectbackground="#0284C7",
            selectmode="extended",
            relief="flat",
        )
        ev_listbox.pack(fill="both", expand=True)

        displayed_events: list[dict] = []

        def _render_events_list(events: list[dict]):
            nonlocal displayed_events
            ev_listbox.delete(0, tk.END)
            deleted_ids = set(cfg.get("google_cal_deleted_ids") or [])
            muted_ids = set(cfg.get("google_cal_muted_ids") or [])
            displayed_events = [ev for ev in events if str(ev.get("id", "")) not in deleted_ids]
            if not displayed_events:
                ev_listbox.insert(tk.END, "جلسه‌ای برای ۷ روز آینده یافت نشد.")
                ev_listbox.itemconfig(0, fg="#94A3B8")
                return
            for idx, ev in enumerate(displayed_events):
                ev_id = str(ev.get("id", ""))
                s_dt: datetime = ev["start"]
                jy, jm, jd = gregorian_to_jalali(s_dt.year, s_dt.month, s_dt.day)
                t_str = "تمام‌روز" if ev.get("all_day") else s_dt.strftime("%H:%M")
                is_muted = ev_id in muted_ids
                icon = "🔕" if is_muted else "🔔"
                suffix = "  (بدون آلارم)" if is_muted else ""
                ev_listbox.insert(tk.END, f"{icon} {jy:04d}/{jm:02d}/{jd:02d}  {t_str}  |  {ev['summary']}{suffix}")
                ev_listbox.itemconfig(idx, fg="#94A3B8" if is_muted else "#A7F3D0")

        def _reapply_alarm_store_from_cache():
            events = getattr(self.app, "_cached_google_events", [])
            sync_google_events_to_alarm_store(events, self.app.alarm_store, cfg)
            self.app._save_config()
            if self.app.alarm_win and self.app.alarm_win.win and self.app.alarm_win.win.winfo_exists():
                self.app.alarm_win._refresh_list()
                self.app.alarm_win._render_picker_calendar()
            if cfg.get("calendar_expanded"):
                self.app._render_calendar_month()
            self.app._refresh_display()
            _render_events_list(events)

        def _toggle_selected_mute(_event=None):
            sel = ev_listbox.curselection()
            if not sel or not displayed_events:
                return
            muted = set(cfg.get("google_cal_muted_ids") or [])
            for idx in sel:
                if 0 <= idx < len(displayed_events):
                    ev_id = str(displayed_events[idx].get("id", ""))
                    if ev_id in muted:
                        muted.remove(ev_id)
                    else:
                        muted.add(ev_id)
            cfg["google_cal_muted_ids"] = list(muted)
            _reapply_alarm_store_from_cache()
            status_var.set("✓ وضعیت آلارم جلسات انتخاب‌شده به‌روزرسانی شد.")

        def _delete_selected_events():
            sel = ev_listbox.curselection()
            if not sel or not displayed_events:
                return
            deleted = set(cfg.get("google_cal_deleted_ids") or [])
            for idx in sel:
                if 0 <= idx < len(displayed_events):
                    deleted.add(str(displayed_events[idx].get("id", "")))
            cfg["google_cal_deleted_ids"] = list(deleted)
            _reapply_alarm_store_from_cache()
            status_var.set("✓ جلسات انتخاب‌شده از لیست و ریمایندر حذف شدند.")

        def _restore_all_events():
            cfg["google_cal_muted_ids"] = []
            cfg["google_cal_deleted_ids"] = []
            _reapply_alarm_store_from_cache()
            status_var.set("✓ همه جلسات و آلارم‌های حذف‌شده/بی‌صدا بازگردانی شدند.")

        ev_listbox.bind("<Double-Button-1>", _toggle_selected_mute)

        ev_actions = tk.Frame(list_box, bg="#1E293B")
        ev_actions.pack(fill="x", pady=(5, 0))
        tk.Button(
            ev_actions,
            text="🔔/🔕 تغییر آلارم انتخاب‌شده",
            font=(font_fa, 7, "bold"),
            bg="#334155",
            fg="#FBBF24",
            padx=8,
            pady=2,
            relief="flat",
            cursor="hand2",
            command=_toggle_selected_mute,
        ).pack(side="right", padx=(4, 0))
        tk.Button(
            ev_actions,
            text="🗑 حذف انتخاب‌شده",
            font=(font_fa, 7, "bold"),
            bg="#7F1D1D",
            fg="#FCA5A5",
            padx=8,
            pady=2,
            relief="flat",
            cursor="hand2",
            command=_delete_selected_events,
        ).pack(side="right", padx=(4, 0))
        tk.Button(
            ev_actions,
            text="♻️ بازگردانی همه",
            font=(font_fa, 7),
            bg="#0F172A",
            fg="#94A3B8",
            padx=8,
            pady=2,
            relief="flat",
            cursor="hand2",
            command=_restore_all_events,
        ).pack(side="left")

        def _save_google_settings():
            cfg["google_cal_enabled"] = bool(enabled_var.get())
            cfg["google_cal_mode"] = mode_var.get()
            cfg["google_cal_ics_url"] = ics_var.get().strip()
            cfg["google_oauth_client_id"] = cid_var.get().strip()
            cfg["google_oauth_client_secret"] = csec_var.get().strip()
            cfg["google_remind_before_enabled"] = bool(before_on_var.get())
            cfg["google_remind_minutes_before"] = int(before_mins_var.get())
            cfg["google_morning_summary_enabled"] = bool(morning_on_var.get())
            cfg["google_morning_summary_time"] = morning_time_var.get().strip() or "09:00"
            cfg["google_cal_sync_minutes"] = max(5, int(sync_mins_var.get()))
            self.app._save_config()

        def _sync_now():
            _save_google_settings()
            status_var.set("⏳ در حال دریافت جلسات از تقویم گوگل...")
            win.update_idletasks()

            def _worker():
                try:
                    ev_list = self.app.sync_google_calendar_now(force=True)
                    win.after(0, lambda: _render_events_list(ev_list))
                    win.after(0, lambda: status_var.set(cfg.get("google_cal_last_status", "✓ همگام‌سازی انجام شد.")))
                except Exception as exc:
                    win.after(0, lambda: status_var.set(f"❌ خطا: {exc}"))

            threading.Thread(target=_worker, daemon=True).start()

        def _disconnect_all():
            ok = messagebox.askyesno(
                "قطع اتصال تقویم گوگل",
                "آیا مطمئن هستید؟\nلینک، توکن گوگل و تمام ریمایندرهای همگام‌سازی‌شده از تقویم گوگل به طور کامل پاک می‌شوند (آلارم‌های شخصی شما حفظ می‌شوند).",
                parent=win,
            )
            if not ok:
                return
            self.app.disconnect_google_calendar()
            enabled_var.set(False)
            ics_var.set("")
            cid_var.set("")
            csec_var.set("")
            _render_events_list([])
            status_var.set("✓ اتصال تقویم گوگل قطع شد و تمام داده‌ها پاک شدند.")

        btn_bar = tk.Frame(main, bg="#0F172A")
        btn_bar.pack(fill="x")
        tk.Button(
            btn_bar,
            text="🔄 همگام‌سازی الان",
            font=(font_fa, 8, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=_sync_now,
        ).pack(side="left")
        tk.Button(
            btn_bar,
            text="💾 ذخیره تنظیمات",
            font=(font_fa, 8, "bold"),
            bg="#10B981",
            fg="#0F172A",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=lambda: (_save_google_settings(), status_var.set("✓ تنظیمات تقویم گوگل ذخیره شد.")),
        ).pack(side="left", padx=6)
        tk.Button(
            btn_bar,
            text="🔌 قطع اتصال و پاک کردن",
            font=(font_fa, 8, "bold"),
            bg="#DC2626",
            fg="#FFFFFF",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=_disconnect_all,
        ).pack(side="left")
        tk.Button(
            btn_bar,
            text="بستن",
            font=(font_fa, 8),
            bg="#334155",
            fg="#F8FAFC",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=win.destroy,
        ).pack(side="right")

        _render_events_list(getattr(self.app, "_cached_google_events", []))
