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
    from src.dev_tools import generate_guid, generate_nanoid, generate_ulid, parse_any_time_input
except ImportError:
    from calendar_data import TEHRAN_TZ, get_today_info, gregorian_to_jalali
    from dev_tools import generate_guid, generate_nanoid, generate_ulid, parse_any_time_input


DEFAULT_API_PORT = 17845

MCP_TOOLS = [
    {
        "name": "get_persian_datetime",
        "description": "دریافت ساعت و تاریخ دقیق شمسی (تهران)، میلادی، UTC، Unix Timestamp، مناسبت روز و وضعیت تعطیلی",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "convert_datetime",
        "description": "تبدیل دقیق هر فرمت زمان (Unix ثانیه/میلی‌ثانیه، ISO-8601، میلادی یا شمسی مثل 1405/08/24 14:30) به تمام فرمت‌ها",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "مقدار زمان ورودی (مثلاً 1763200000 یا 1405/08/24 14:30 یا 2026-11-15T12:00:00Z)"}
            },
            "required": ["value"],
        },
    },
    {
        "name": "get_ip_location_status",
        "description": "دریافت IP عمومی فعلی سیستم، شهر، کشور، وضعیت قفل لوکیشن و تاریخچه تغییرات ۳ روز گذشته",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "toggle_ip_lock",
        "description": "فعال یا غیرفعال کردن قفل شهر/IP روی موقعیت فعلی سیستم برای جلوگیری از تغییر ناگهانی IP",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "true برای قفل کردن روی موقعیت فعلی، false برای باز کردن قفل"},
                "mode": {"type": "string", "enum": ["city", "ip", "both"], "description": "حالت قفل (پیش‌فرض city)"},
            },
            "required": ["enabled"],
        },
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
        "name": "delete_alarm",
        "description": "حذف یک آلارم یا یادآور ثبت‌شده با شناسه (id)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "شناسه آلارم برای حذف"},
            },
            "required": ["id"],
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
    {
        "name": "stop_pomodoro_timer",
        "description": "توقف تایمر پومودورو فعال روی ویجت",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_dev_ids",
        "description": "تولید هم‌زمان UUID v4، ULID و NanoID برای تست API و دیتابیس",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
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
        self.started_at: float | None = None
        self.recent_logs: list[dict] = []
        self._log_lock = threading.Lock()

    def _add_log(self, method: str, path: str, status: int, detail: str = ""):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "method": method,
            "path": path,
            "status": status,
            "detail": detail,
        }
        with self._log_lock:
            self.recent_logs.insert(0, entry)
            self.recent_logs = self.recent_logs[:30]

    def get_logs(self) -> list[dict]:
        with self._log_lock:
            return list(self.recent_logs)

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
            "unix_ms": int(time.time() * 1000),
            "is_holiday": bool(info.get("is_holiday")),
            "occasion": info.get("occasion") or "",
        }

    def _convert_datetime(self, body: dict) -> dict:
        raw = str(body.get("value") or "").strip()
        if not raw:
            raise ValueError("فیلد value الزامی است")
        res = parse_any_time_input(raw)
        return {"ok": True, "input": raw, "converted": res}

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

    def _toggle_ip_lock(self, body: dict) -> dict:
        enabled = bool(body.get("enabled", True))
        mode = str(body.get("mode") or self.app.config.get("ip_lock_mode", "city")).strip().lower()
        if mode not in ("city", "ip", "both"):
            mode = "city"

        def _apply():
            self.app.config["ip_lock_mode"] = mode
            if enabled:
                info = getattr(self.app, "_ip_info", {}) or {}
                self.app.config["ip_lock_enabled"] = True
                self.app.config["ip_locked_city"] = info.get("city", "") or self.app.config.get("ip_locked_city", "")
                self.app.config["ip_locked_country"] = info.get("country_code", "") or self.app.config.get("ip_locked_country", "")
                self.app.config["ip_locked_ip"] = info.get("ip", "") or self.app.config.get("ip_locked_ip", "")
            else:
                self.app.config["ip_lock_enabled"] = False
                self.app._ip_alert_active = False
            self.app._save_config()
            self.app._refresh_ip_window_labels()
            return {
                "ok": True,
                "lock_enabled": self.app.config["ip_lock_enabled"],
                "lock_mode": mode,
                "locked_city": self.app.config.get("ip_locked_city", ""),
                "locked_ip": self.app.config.get("ip_locked_ip", ""),
            }

        return self._run_on_ui(_apply)

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

    def _delete_alarm(self, body: dict) -> dict:
        alarm_id = str(body.get("id") or "").strip()
        if not alarm_id:
            raise ValueError("شناسه آلارم (id) الزامی است")

        def _del():
            before = len(self.app.alarm_store.alarms)
            self.app.alarm_store.delete_alarm(alarm_id)
            after = len(self.app.alarm_store.alarms)
            self.app._refresh_display()
            return {"ok": True, "deleted": before != after, "id": alarm_id}

        return self._run_on_ui(_del)

    def _start_timer(self, body: dict) -> dict:
        minutes = max(1, min(240, int(body.get("minutes", 25))))
        label = str(body.get("label") or "Deep Work").strip()

        def _go():
            self.app.start_pomodoro_timer(minutes=minutes, label=label)
            return {"ok": True, "minutes": minutes, "label": label}

        return self._run_on_ui(_go)

    def _stop_timer(self) -> dict:
        def _stop():
            self.app.stop_pomodoro_timer()
            return {"ok": True, "stopped": True}

        return self._run_on_ui(_stop)

    @staticmethod
    def _generate_ids() -> dict:
        return {
            "ok": True,
            "uuid_v4": generate_guid(),
            "ulid": generate_ulid(),
            "nanoid": generate_nanoid(),
        }

    def _handle_mcp(self, rpc: dict) -> tuple[dict, str]:
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
            }, "initialize"
        if method == "notifications/initialized":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}, "notifications/initialized"
        if method == "ping":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}, "ping"
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": MCP_TOOLS}}, "tools/list"
        if method == "tools/call":
            t_name = params.get("name", "")
            args = params.get("arguments") or {}
            if t_name == "get_persian_datetime":
                res = self._get_now_payload()
            elif t_name == "convert_datetime":
                res = self._convert_datetime(args)
            elif t_name == "get_ip_location_status":
                res = self._get_ip_payload()
            elif t_name == "toggle_ip_lock":
                res = self._toggle_ip_lock(args)
            elif t_name == "list_alarms":
                res = self._list_alarms_payload()
            elif t_name == "schedule_reminder":
                res = self._schedule_alarm(args)
            elif t_name == "delete_alarm":
                res = self._delete_alarm(args)
            elif t_name == "start_pomodoro_timer":
                res = self._start_timer(args)
            elif t_name == "stop_pomodoro_timer":
                res = self._stop_timer()
            elif t_name == "generate_dev_ids":
                res = self._generate_ids()
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {t_name}"},
                }, f"tools/call:{t_name}"
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]},
            }, f"tools/call:{t_name}"
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}, method

    def start(self, port: int | None = None) -> bool:
        if port is not None:
            self.port = int(port)
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
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _read_json(self) -> dict:
                ln = int(self.headers.get("Content-Length", "0") or 0)
                if ln <= 0:
                    return {}
                raw = self.rfile.read(ln).decode("utf-8", errors="replace")
                return json.loads(raw)

            def do_OPTIONS(self):
                self._send_json(200, {"ok": True})

            def do_GET(self):
                try:
                    if self.path == "/health":
                        uptime = int(time.time() - api_ref.started_at) if api_ref.started_at else 0
                        self._send_json(200, {"ok": True, "app": "PersianClockWidget", "version": "2.0.0", "tools_count": len(MCP_TOOLS), "uptime_seconds": uptime})
                        api_ref._add_log("GET", "/health", 200)
                    elif self.path == "/now":
                        self._send_json(200, api_ref._get_now_payload())
                        api_ref._add_log("GET", "/now", 200)
                    elif self.path == "/ip":
                        self._send_json(200, api_ref._get_ip_payload())
                        api_ref._add_log("GET", "/ip", 200)
                    elif self.path == "/alarms":
                        self._send_json(200, api_ref._list_alarms_payload())
                        api_ref._add_log("GET", "/alarms", 200)
                    elif self.path == "/dev/ids":
                        self._send_json(200, api_ref._generate_ids())
                        api_ref._add_log("GET", "/dev/ids", 200)
                    elif self.path == "/logs":
                        self._send_json(200, {"ok": True, "logs": api_ref.get_logs()})
                    else:
                        self._send_json(404, {"ok": False, "error": "Not found"})
                        api_ref._add_log("GET", self.path, 404)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                    api_ref._add_log("GET", self.path, 500, str(exc))

            def do_POST(self):
                try:
                    body = self._read_json()
                    if self.path == "/alarms":
                        self._send_json(200, api_ref._schedule_alarm(body))
                        api_ref._add_log("POST", "/alarms", 200, str(body.get("title", "")))
                    elif self.path == "/alarms/delete":
                        self._send_json(200, api_ref._delete_alarm(body))
                        api_ref._add_log("POST", "/alarms/delete", 200, str(body.get("id", "")))
                    elif self.path == "/convert":
                        self._send_json(200, api_ref._convert_datetime(body))
                        api_ref._add_log("POST", "/convert", 200, str(body.get("value", "")))
                    elif self.path == "/ip/lock":
                        self._send_json(200, api_ref._toggle_ip_lock(body))
                        api_ref._add_log("POST", "/ip/lock", 200, str(body.get("enabled", "")))
                    elif self.path == "/timer":
                        self._send_json(200, api_ref._start_timer(body))
                        api_ref._add_log("POST", "/timer", 200, f"{body.get('minutes', 25)}m")
                    elif self.path == "/timer/stop":
                        self._send_json(200, api_ref._stop_timer())
                        api_ref._add_log("POST", "/timer/stop", 200)
                    elif self.path == "/mcp":
                        resp, detail = api_ref._handle_mcp(body)
                        self._send_json(200, resp)
                        api_ref._add_log("POST", "/mcp", 200, detail)
                    else:
                        self._send_json(404, {"ok": False, "error": "Not found"})
                        api_ref._add_log("POST", self.path, 404)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                    api_ref._add_log("POST", self.path, 500, str(exc))

        try:
            self._server = _ReusableThreadingHTTPServer(("127.0.0.1", self.port), Handler)
            self.running = True
            self.started_at = time.time()
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
        self.started_at = None
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
