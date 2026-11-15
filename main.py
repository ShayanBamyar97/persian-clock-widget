#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نقطه ورود اصلی برنامه (Main Entry Point)
ویجت ساعت تهران، تقویم شمسی، مناسبت‌ها و سیستم یادآور ویندوز
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

import os
import sys

# افزودن پوشه ریشه پروژه به مسیر جستجوی ماژول‌ها
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.widget import PersianClockWidget

_INSTANCE_LOCK_HANDLE = None


def _acquire_single_instance_lock() -> bool:
    """جلوگیری از اجرای هم‌زمان چند نسخه از ویجت روی سیستم"""
    global _INSTANCE_LOCK_HANDLE
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            mutex_name = "Local\\PersianClockWidget_SingleInstance_Mutex_v1"
            handle = kernel32.CreateMutexW(None, False, mutex_name)
            last_err = kernel32.GetLastError()
            if handle:
                _INSTANCE_LOCK_HANDLE = handle
            if last_err == 183:  # ERROR_ALREADY_EXISTS
                try:
                    hwnd = user32.FindWindowW(None, "ویجت ساعت و تقویم")
                    if hwnd and user32.IsWindowVisible(hwnd):
                        user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                return False
        except Exception:
            pass
        return True

    try:
        import fcntl

        lock_path = os.path.join(os.path.expanduser("~"), ".persian_clock_widget.lock")
        fp = open(lock_path, "w", encoding="utf-8")
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _INSTANCE_LOCK_HANDLE = fp
        return True
    except Exception:
        return False


def main():
    if not _acquire_single_instance_lock():
        return
    app = PersianClockWidget()
    app.run()


if __name__ == "__main__":
    main()
