# -*- coding: utf-8 -*-
"""
سرور محلی HTTP API و MCP (JSON-RPC 2.0) برای اتصال مستقیم ابزارهای AI و اسکریپت‌ها به ویجت
فقط روی آدرس محلی 127.0.0.1 اجرا می‌شود.
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

try:
    from src.calendar_data import TEHRAN_TZ, get_today_info, gregorian_to_jalali
except ImportError:
    from calendar_data import TEHRAN_TZ, get_today_info, gregorian_to_jalali


DEFAULT_API_PORT = 17845

MCP_TOOLS = [
    {
        "name": "get_persian_datetime",
        "description": "دریافت ساعت و تاریخ دقیق شمسی (تهران)، میلادی، UTC، Unix Timestamp، مناسبت روز و وضعیت تعطیلی",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_ip_location_status",
        "description": "دریافت IP عمومی فعلی سیستم، شهر، کشور، وضعیت قفل لوکیشن و تاریخچه تغییرات ۳ روز گذشته",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_alarms",
        "description": "نمایش لیست رویدادها و آلارم‌های ثبت‌شده در ویجت",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "schedule_reminder",
        "description": "ثبت یک یادآور یا آلارم جدید در ویجت (با in_minutes یا تاریخ شمسی و ساعت/دقیقه و اکشن اختیاری url/webhook/command)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "عنوان یادآور یا رویداد"},
                "message": {"type": "string", "description": "توضیحات اختیاری"},
                "in_minutes": {"type": "integer", "description": "چند دقیقه بعد از الان اجرا شود (مثلاً 25)"},
                "jalali_date": {"type": "string", "description": "تاریخ شمسی به فرمت YYYY/MM/DD (در صورت عدم استفاده از in_minutes)"},
                "hour": {"type": "integer", "description": "ساعت (0 تا 23)"},
                "minute": {"type": "integer", "description": "دقیقه (0 تا 59)"},
                "action_type": {"type": "string", "enum": ["none", "url", "webhook", "command"]},
                "action_target": {"type": "string", "description": "لینک، آدرس Webhook یا دستور اجرایی"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "start_pomodoro_timer",
        "description": "شروع تایمر تمرکز / پومودورو روی ویجت برای مدت مشخص (برحسب دقیقه)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "مدت زمان به دقیقه (پیش‌فرض 25)"},
                "label": {"type": "string", "description": "عنوان تایمر"},
            },
            "required": [],
        },
    },
]


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class LocalWidgetApiServer:
    """مدیریت سرور محلی HTTP + MCP روی 127.0.0.1"""

    def __init__(self, app, port: int = DEFAULT_API_PORT):
        self.app = app
        self.port = int(port)
        self._server: _ReusableThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.running = False
        self.last_error = ""

    def _run_on_ui(self, fn, timeout: float = 3.0):
        done = threading.Event()
        box: dict = {"res": None, "err": None}

        def _task():
            try:
                box["res"] = fn()
            except Exception as exc:
                box["err"] = exc
            finally:
                done.set()

        self.app.root.after(0, _task)
        done.wait(timeout=timeout)
        if box["err"] is not None:
            raise box["err"]
        return box["res"]

    def _get_now_payload(self) -> dict:
        info = get_today_info()
        now_utc = datetime.now(timezone.utc)
        return {
            "ok": True,
            "jalali_date": f"{info['jy']:04d}/{info['jm']:02d}/{info['jd']:02d}",
            "date_text": info["date_text"],
            "tehran_time": f"{info['time_str']}:{int(info['second']):02d}",
            "utc_iso": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "unix_seconds": int(time.time()),
            "is_holiday": bool(info.get("is_holiday")),
            "occasion": info.get("occasion") or "",
        }

    def _get_ip_payload(self) -> dict:
        def _read():
            return {
                "ok": True,
                "current": dict(getattr(self.app, "_ip_info", {}) or {}),
                "lock_enabled": bool(self.app.config.get("ip_lock_enabled", False)),
                "lock_mode": self.app.config.get("ip_lock_mode", "city"),
                "locked_city": self.app.config.get("ip_locked_city", ""),
                "locked_ip": self.app.config.get("ip_locked_ip", ""),
                "alert_active": bool(getattr(self.app, "_ip_alert_active", False)),
                "changes_3d": self.app.ip_history_store.get_change_count(),
                "history_3d": self.app.ip_history_store.get_recent_entries(),
            }

        return self._run_on_ui(_read)

    def _list_alarms_payload(self) -> dict:
        def _read():
            return {"ok": True, "alarms": list(self.app.alarm_store.alarms)}

        return self._run_on_ui(_read)

    def _schedule_alarm(self, body: dict) -> dict:
        title = str(body.get("title") or "یادآور AI").strip()
        message = str(body.get("message") or "").strip()
        action_type = str(body.get("action_type") or "none").strip().lower()
        action_target = str(body.get("action_target") or "").strip()

        if body.get("in_minutes") is not None:
            mins = max(1, int(body["in_minutes"]))
            target_dt = datetime.now(TEHRAN_TZ) + timedelta(minutes=mins)
            jy, jm, jd = gregorian_to_jalali(target_dt.year, target_dt.month, target_dt.day)
            j_date = f"{jy:04d}/{jm:02d}/{jd:02d}"
            hour = target_dt.hour
            minute = target_dt.minute
        else:
            now_teh = datetime.now(TEHRAN_TZ)
            jy, jm, jd = gregorian_to_jalali(now_teh.year, now_teh.month, now_teh.day)
            j_date = str(body.get("jalali_date") or f"{jy:04d}/{jm:02d}/{jd:02d}").strip()
            hour = int(body.get("hour", now_teh.hour))
            minute = int(body.get("minute", now_teh.minute))

        def _add():
            alarm = self.app.alarm_store.add_alarm(
                title=title,
                hour=hour,
                minute=minute,
                repeat="once",
                dates=[j_date],
                play_sound=True,
                message=message,
                action_type=action_type,
                action_target=action_target,
            )
            self.app._refresh_display()
            return alarm

        created = self._run_on_ui(_add)
        return {"ok": True, "alarm": created}

    def _start_timer(self, body: dict) -> dict:
        minutes = max(1, min(240, int(body.get("minutes", 25))))
        label = str(body.get("label") or "Deep Work").strip()

        def _go():
            self.app.start_pomodoro_timer(minutes=minutes, label=label)
            return {"ok": True, "minutes": minutes, "label": label}

        return self._run_on_ui(_go)

    def _handle_mcp(self, rpc: dict) -> dict:
        rpc_id = rpc.get("id")
        method = rpc.get("method", "")
        params = rpc.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "persian-clock-widget", "version": "2.0.0"},
                },
            }
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": MCP_TOOLS}}
        if method == "tools/call":
            t_name = params.get("name", "")
            args = params.get("arguments") or {}
            if t_name == "get_persian_datetime":
                res = self._get_now_payload()
            elif t_name == "get_ip_location_status":
                res = self._get_ip_payload()
            elif t_name == "list_alarms":
                res = self._list_alarms_payload()
            elif t_name == "schedule_reminder":
                res = self._schedule_alarm(args)
            elif t_name == "start_pomodoro_timer":
                res = self._start_timer(args)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {t_name}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]},
            }
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    def start(self) -> bool:
        if self.running:
            return True
        api_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def _send_json(self, code: int, data: dict):
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _read_json(self) -> dict:
                ln = int(self.headers.get("Content-Length", "0") or 0)
                if ln <= 0:
                    return {}
                raw = self.rfile.read(ln).decode("utf-8", errors="replace")
                return json.loads(raw)

            def do_GET(self):
                try:
                    if self.path == "/health":
                        self._send_json(200, {"ok": True, "app": "PersianClockWidget", "version": "2.0.0"})
                    elif self.path == "/now":
                        self._send_json(200, api_ref._get_now_payload())
                    elif self.path == "/ip":
                        self._send_json(200, api_ref._get_ip_payload())
                    elif self.path == "/alarms":
                        self._send_json(200, api_ref._list_alarms_payload())
                    else:
                        self._send_json(404, {"ok": False, "error": "Not found"})
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})

            def do_POST(self):
                try:
                    body = self._read_json()
                    if self.path == "/alarms":
                        self._send_json(200, api_ref._schedule_alarm(body))
                    elif self.path == "/timer":
                        self._send_json(200, api_ref._start_timer(body))
                    elif self.path == "/mcp":
                        self._send_json(200, api_ref._handle_mcp(body))
                    else:
                        self._send_json(404, {"ok": False, "error": "Not found"})
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})

        try:
            self._server = _ReusableThreadingHTTPServer(("127.0.0.1", self.port), Handler)
            self.running = True
            self.last_error = ""
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            return True
        except Exception as exc:
            self.running = False
            self.last_error = str(exc)
            return False

    def stop(self):
        self.running = False
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
