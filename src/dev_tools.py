# -*- coding: utf-8 -*-
"""
ابزارهای حرفه‌ای برنامه‌نویسان (نسخه ۲):
- تحلیل و پیش‌بینی اجرای بعدی Cron (به وقت تهران و UTC)
- مبدل دوطرفه Unix Timestamp / ISO-8601 / تاریخ شمسی
- دیکدر آفلاین توکن JWT و بررسی زمان انقضا
- تولیدکننده ULID و NanoID و GUID
- برنامه‌ریز ساعت جلسات بین تایم‌زون‌های تیمی

طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

import base64
from datetime import datetime, timedelta, timezone
import json
import os
import re
import secrets
import time
import uuid
from zoneinfo import ZoneInfo

try:
    from src.calendar_data import TEHRAN_TZ, gregorian_to_jalali, jalali_to_gregorian
except ImportError:
    from calendar_data import TEHRAN_TZ, gregorian_to_jalali, jalali_to_gregorian


_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_NANOID_ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-"

CRON_PRESETS: list[tuple[str, str]] = [
    ("هر ۵ دقیقه", "*/5 * * * *"),
    ("هر ساعت (دقیقه ۰)", "0 * * * *"),
    ("هر روز ۰۹:۰۰", "0 9 * * *"),
    ("روزهای کاری (دوشنبه-جمعه) ۰۹:۰۰", "0 9 * * 1-5"),
    ("هر شب ۰۲:۰۰", "0 2 * * *"),
    ("اول هر ماه ۰۰:۰۰", "0 0 1 * *"),
]


def generate_guid() -> str:
    return str(uuid.uuid4())


def generate_ulid() -> str:
    """تولید ULID استاندارد ۲۶ کاراکتری (مرتب‌سازی زمانی + ۸۰ بیت تصادفی)"""
    ts_ms = int(time.time() * 1000)
    time_chars = []
    for _ in range(10):
        time_chars.append(_CROCKFORD32[ts_ms & 31])
        ts_ms >>= 5
    time_part = "".join(reversed(time_chars))

    rand_val = int.from_bytes(os.urandom(10), "big")
    rand_chars = []
    for _ in range(16):
        rand_chars.append(_CROCKFORD32[rand_val & 31])
        rand_val >>= 5
    rand_part = "".join(reversed(rand_chars))
    return time_part + rand_part


def generate_nanoid(size: int = 21) -> str:
    """تولید NanoID امن و کوتاه"""
    return "".join(secrets.choice(_NANOID_ALPHA) for _ in range(max(8, min(64, int(size)))))


def _parse_cron_field(field: str, min_val: int, max_val: int, is_dow: bool = False) -> set[int]:
    """تجزیه یک فیلد استاندارد Cron (*, */n, a-b, a,b, a-b/n)"""
    out: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("فیلد خالی در Cron")
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError("گام باید بزرگ‌تر از صفر باشد")
        else:
            base, step = part, 1

        if base == "*":
            start, end = min_val, max_val
        elif "-" in base:
            a_s, b_s = base.split("-", 1)
            start, end = int(a_s), int(b_s)
        else:
            val = int(base)
            if is_dow and val == 7:
                val = 0
            if val < min_val or val > max_val:
                raise ValueError(f"مقدار {val} خارج از بازه {min_val}..{max_val} است")
            out.add(val)
            continue

        if is_dow and end == 7:
            end = 7
        if start < min_val or end > (7 if is_dow else max_val) or start > end:
            raise ValueError(f"بازه نامعتبر: {base}")
        for v in range(start, end + 1, step):
            out.add(0 if (is_dow and v == 7) else v)
    return out


def parse_cron_expression(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError("عبارت Cron باید دقیقاً ۵ بخش داشته باشد (دقیقه ساعت روز ماه روزهفته)")
    mins = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    doms = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    dows = _parse_cron_field(parts[4], 0, 7, is_dow=True)
    return mins, hours, doms, months, dows


def describe_cron_fa(expr: str) -> str:
    """توضیح خوانای فارسی برای عبارت ۵ بخشی Cron"""
    try:
        parts = expr.strip().split()
        if len(parts) != 5:
            return "فرمت نامعتبر (باید ۵ بخش با فاصله باشد)"
        m, h, dom, mon, dow = parts
        parse_cron_expression(expr)
        segs = []
        if m.startswith("*/"):
            segs.append(f"هر {m[2:]} دقیقه")
        elif m == "*":
            segs.append("هر دقیقه")
        else:
            segs.append(f"دقیقه {m}")

        if h.startswith("*/"):
            segs.append(f"هر {h[2:]} ساعت")
        elif h != "*":
            segs.append(f"ساعت {h}")

        if dom != "*":
            segs.append(f"روز {dom} ماه")
        if mon != "*":
            segs.append(f"ماه {mon}")
        if dow == "1-5":
            segs.append("دوشنبه تا جمعه")
        elif dow != "*":
            segs.append(f"روز هفته {dow}")
        return " • ".join(segs)
    except Exception as exc:
        return f"خطا: {exc}"


def next_cron_runs(expr: str, count: int = 5, tz_mode: str = "tehran") -> list[dict]:
    """محاسبه N زمان اجرای بعدی Cron در تایم‌زون تهران یا UTC"""
    mins, hours, doms, months, dows = parse_cron_expression(expr)
    parts = expr.strip().split()
    dom_wild = parts[2] == "*"
    dow_wild = parts[4] == "*"

    tz = TEHRAN_TZ if tz_mode == "tehran" else timezone.utc
    cur = datetime.now(tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = cur + timedelta(days=366)
    results: list[dict] = []

    while cur <= limit and len(results) < count:
        if cur.month not in months:
            # پرش سریع به اول ماه بعدی
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1, day=1, hour=0, minute=0)
            else:
                cur = cur.replace(month=cur.month + 1, day=1, hour=0, minute=0)
            continue

        # در استاندارد Cron: 0 = Sunday .. 6 = Saturday
        cron_dow = (cur.weekday() + 1) % 7
        dom_match = cur.day in doms
        dow_match = cron_dow in dows
        day_ok = (dom_match and dow_match) if (dom_wild or dow_wild) else (dom_match or dow_match)
        if not day_ok:
            cur = (cur + timedelta(days=1)).replace(hour=0, minute=0)
            continue

        if cur.hour not in hours:
            cur = (cur + timedelta(hours=1)).replace(minute=0)
            continue

        if cur.minute in mins:
            dt_teh = cur.astimezone(TEHRAN_TZ)
            dt_utc = cur.astimezone(timezone.utc)
            jy, jm, jd = gregorian_to_jalali(dt_teh.year, dt_teh.month, dt_teh.day)
            results.append(
                {
                    "tehran": f"{jy:04d}/{jm:02d}/{jd:02d} {dt_teh.strftime('%H:%M')}",
                    "utc": dt_utc.strftime("%Y-%m-%d %H:%M UTC"),
                    "greg": dt_teh.strftime("%Y-%m-%d %H:%M"),
                }
            )
        cur += timedelta(minutes=1)
    return results


def parse_any_time_input(raw: str) -> dict:
    """تبدیل خودکار Unix (ثانیه/میلی‌ثانیه)، ISO-8601 یا تاریخ شمسی به همه فرمت‌ها"""
    s = raw.strip()
    if not s:
        raise ValueError("ورودی خالی است")

    dt_utc: datetime | None = None

    # ۱. عدد خالص (Unix seconds یا milliseconds)
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        val = float(s)
        if abs(val) > 1e11:  # میلی‌ثانیه
            val = val / 1000.0
        dt_utc = datetime.fromtimestamp(val, tz=timezone.utc)
    else:
        # ۲. تاریخ شمسی مثل 1405/08/24 یا 1405/08/24 14:30:00
        jm_match = re.fullmatch(r"(1[34]\d{2})[/\-](\d{1,2})[/\-](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", s)
        if jm_match:
            jy, jm, jd = int(jm_match.group(1)), int(jm_match.group(2)), int(jm_match.group(3))
            hh = int(jm_match.group(4) or 0)
            mm = int(jm_match.group(5) or 0)
            ss = int(jm_match.group(6) or 0)
            gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
            dt_teh = datetime(gy, gm, gd, hh, mm, ss, tzinfo=TEHRAN_TZ)
            dt_utc = dt_teh.astimezone(timezone.utc)
        else:
            # ۳. ISO-8601 یا تاریخ میلادی
            iso_s = s.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(iso_s)
            except Exception:
                dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TEHRAN_TZ)
            dt_utc = dt.astimezone(timezone.utc)

    dt_teh = dt_utc.astimezone(TEHRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(dt_teh.year, dt_teh.month, dt_teh.day)
    unix_sec = int(dt_utc.timestamp())
    return {
        "jalali": f"{jy:04d}/{jm:02d}/{jd:02d} {dt_teh.strftime('%H:%M:%S')}",
        "tehran": dt_teh.strftime("%Y-%m-%d %H:%M:%S (+03:30)"),
        "utc_iso": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unix_s": str(unix_sec),
        "unix_ms": str(int(dt_utc.timestamp() * 1000)),
    }


def _b64url_json(seg: str) -> dict:
    padded = seg + "=" * (-len(seg) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def decode_jwt_offline(token: str) -> dict:
    """دیکد آفلاین JWT (بدون ارسال به اینترنت) همراه با تبدیل زمان‌های iat/exp به شمسی"""
    t = token.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    parts = t.split(".")
    if len(parts) < 2:
        raise ValueError("فرمت JWT نامعتبر است (باید حداقل ۲ بخش با نقطه داشته باشد)")
    header = _b64url_json(parts[0])
    payload = _b64url_json(parts[1])

    def _fmt_ts(val) -> str:
        if not isinstance(val, (int, float)):
            return "—"
        dt_teh = datetime.fromtimestamp(float(val), tz=TEHRAN_TZ)
        jy, jm, jd = gregorian_to_jalali(dt_teh.year, dt_teh.month, dt_teh.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d} {dt_teh.strftime('%H:%M:%S')}"

    exp_status = "بدون فیلد exp"
    is_expired = False
    exp_val = payload.get("exp")
    if isinstance(exp_val, (int, float)):
        diff = int(float(exp_val) - time.time())
        if diff <= 0:
            is_expired = True
            mins = abs(diff) // 60
            hrs, rem_m = divmod(mins, 60)
            exp_status = f"منقضی شده ({hrs} ساعت و {rem_m} دقیقه پیش)" if hrs else f"منقضی شده ({rem_m} دقیقه پیش)"
        else:
            mins = diff // 60
            hrs, rem_m = divmod(mins, 60)
            days, rem_h = divmod(hrs, 24)
            if days:
                exp_status = f"معتبر • {days} روز و {rem_h} ساعت مانده"
            elif hrs:
                exp_status = f"معتبر • {hrs} ساعت و {rem_m} دقیقه مانده"
            else:
                exp_status = f"معتبر • {rem_m} دقیقه و {diff % 60} ثانیه مانده"

    return {
        "header": header,
        "payload": payload,
        "iat_jalali": _fmt_ts(payload.get("iat")),
        "exp_jalali": _fmt_ts(exp_val),
        "exp_status": exp_status,
        "is_expired": is_expired,
        "sub": str(payload.get("sub", "—")),
    }


MEETING_CITIES: list[tuple[str, str]] = [
    ("تهران", "Asia/Tehran"),
    ("UTC", "UTC"),
    ("لندن", "Europe/London"),
    ("برلین / آمستردام", "Europe/Berlin"),
    ("دبی", "Asia/Dubai"),
    ("نیویورک", "America/New_York"),
    ("تورنتو", "America/Toronto"),
]


def convert_tehran_meeting_time(hour: int, minute: int) -> list[dict]:
    """تبدیل یک ساعت مشخص به وقت تهران به ساعت سایر شهرهای تیمی"""
    now_teh = datetime.now(TEHRAN_TZ)
    base_teh = now_teh.replace(hour=int(hour) % 24, minute=int(minute) % 60, second=0, microsecond=0)
    rows: list[dict] = []
    for label, tz_name in MEETING_CITIES:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = TEHRAN_TZ if tz_name == "Asia/Tehran" else timezone.utc
        dt = base_teh.astimezone(tz)
        day_diff = (dt.date() - base_teh.date()).days
        suffix = " (فردا)" if day_diff > 0 else (" (دیروز)" if day_diff < 0 else "")
        rows.append(
            {
                "city": label,
                "tz": tz_name,
                "time": dt.strftime("%H:%M") + suffix,
                "date": dt.strftime("%Y-%m-%d"),
            }
        )
    return rows
