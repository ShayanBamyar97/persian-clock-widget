# -*- coding: utf-8 -*-
"""
اجرای خودکار اکشن‌های زمان‌بندی‌شده (URL / Webhook / Command) برای رویدادها و آلارم‌ها
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

import json
import subprocess
import threading
import urllib.request
import webbrowser


def execute_scheduled_action(alarm: dict, on_result=None):
    """اجرای غیرمسدودکننده اکشن متصل به یک آلارم یا رویداد"""
    action_type = (alarm.get("action_type") or "none").strip().lower()
    target = (alarm.get("action_target") or "").strip()
    if action_type == "none" or not target:
        return

    def _run():
        msg = ""
        ok = True
        try:
            if action_type == "url":
                webbrowser.open(target)
                msg = f"لینک باز شد: {target}"
            elif action_type == "webhook":
                payload = json.dumps(
                    {
                        "event": "persian_clock_alarm",
                        "title": alarm.get("title", ""),
                        "message": alarm.get("message", ""),
                        "hour": alarm.get("hour"),
                        "minute": alarm.get("minute"),
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                req = urllib.request.Request(
                    target,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "PersianClockWidget/2.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    msg = f"Webhook ارسال شد (HTTP {resp.status})"
            elif action_type == "command":
                subprocess.Popen(target, shell=True)
                msg = f"دستور اجرا شد: {target}"
            else:
                ok = False
                msg = f"نوع اکشن ناشناخته: {action_type}"
        except Exception as exc:
            ok = False
            msg = f"خطا در اجرای اکشن: {exc}"

        if on_result:
            try:
                on_result(ok, msg)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
