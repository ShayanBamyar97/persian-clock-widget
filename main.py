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


def main():
    app = PersianClockWidget()
    app.run()


if __name__ == "__main__":
    main()
