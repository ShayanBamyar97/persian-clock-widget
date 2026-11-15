# -*- coding: utf-8 -*-
"""
ماژول پایش دقیق IP عمومی و موقعیت مکانی (شهر/کشور/ISP) و قفل روی شهر یا IP
طراحی و توسعه: شایان بامیار (® Shayan Bamyar)
"""

from datetime import datetime
import json
import urllib.request


def _http_get_json(url: str, timeout: float = 4.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PersianClockWidget/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def fetch_ip_geolocation(timeout: float = 4.0) -> dict:
    """دریافت IP عمومی فعلی و موقعیت جغرافیایی دقیق (شهر، استان، کشور، ISP)"""
    now_str = datetime.now().strftime("%H:%M:%S")

    # ۱. سرویس اول: ip-api.com (دقیق و سریع)
    try:
        d = _http_get_json(
            "http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,isp,query,timezone,lat,lon",
            timeout=timeout,
        )
        if d.get("status") == "success" and d.get("query"):
            return {
                "ok": True,
                "ip": str(d.get("query", "")).strip(),
                "city": str(d.get("city", "")).strip(),
                "region": str(d.get("regionName", "")).strip(),
                "country": str(d.get("country", "")).strip(),
                "country_code": str(d.get("countryCode", "")).strip(),
                "isp": str(d.get("isp", "")).strip(),
                "timezone": str(d.get("timezone", "")).strip(),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
                "checked_at": now_str,
            }
    except Exception:
        pass

    # ۲. سرویس پشتیبان: ipwho.is
    try:
        d = _http_get_json("https://ipwho.is/", timeout=timeout)
        if d.get("success") and d.get("ip"):
            conn = d.get("connection") or {}
            tz = d.get("timezone") or {}
            return {
                "ok": True,
                "ip": str(d.get("ip", "")).strip(),
                "city": str(d.get("city", "")).strip(),
                "region": str(d.get("region", "")).strip(),
                "country": str(d.get("country", "")).strip(),
                "country_code": str(d.get("country_code", "")).strip(),
                "isp": str(conn.get("isp", "") or conn.get("org", "")).strip(),
                "timezone": str(tz.get("id", "")).strip(),
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "checked_at": now_str,
            }
    except Exception:
        pass

    # ۳. سرویس پشتیبان: ipapi.co
    try:
        d = _http_get_json("https://ipapi.co/json/", timeout=timeout)
        if d.get("ip") and not d.get("error"):
            return {
                "ok": True,
                "ip": str(d.get("ip", "")).strip(),
                "city": str(d.get("city", "")).strip(),
                "region": str(d.get("region", "")).strip(),
                "country": str(d.get("country_name", "")).strip(),
                "country_code": str(d.get("country_code", "")).strip(),
                "isp": str(d.get("org", "")).strip(),
                "timezone": str(d.get("timezone", "")).strip(),
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "checked_at": now_str,
            }
    except Exception:
        pass

    return {
        "ok": False,
        "ip": "",
        "city": "",
        "region": "",
        "country": "",
        "country_code": "",
        "isp": "",
        "timezone": "",
        "lat": None,
        "lon": None,
        "checked_at": now_str,
    }


def check_ip_lock_mismatch(info: dict, config: dict) -> tuple[bool, str]:
    """بررسی تغییر IP یا شهر نسبت به مقدار قفل‌شده"""
    if not config.get("ip_lock_enabled", False):
        return False, ""
    if not info or not info.get("ok"):
        return False, ""

    mode = config.get("ip_lock_mode", "city")
    cur_ip = (info.get("ip") or "").strip()
    cur_city = (info.get("city") or "").strip()
    cur_cc = (info.get("country_code") or "").strip()

    locked_ip = (config.get("ip_locked_ip") or "").strip()
    locked_city = (config.get("ip_locked_city") or "").strip()
    locked_cc = (config.get("ip_locked_country") or "").strip()

    if mode == "ip":
        if locked_ip and cur_ip != locked_ip:
            return True, f"IP تغییر کرد: {locked_ip} ⟵ {cur_ip} ({cur_city or cur_cc})"
        return False, ""

    if mode == "both":
        reasons = []
        if locked_city and cur_city.lower() != locked_city.lower():
            reasons.append(f"شهر: {locked_city} ⟵ {cur_city or 'نامشخص'}")
        if locked_ip and cur_ip != locked_ip:
            reasons.append(f"IP: {locked_ip} ⟵ {cur_ip}")
        if reasons:
            return True, " | ".join(reasons)
        return False, ""

    # پیش‌فرض: قفل روی شهر (city)
    if locked_city:
        if cur_city.lower() != locked_city.lower():
            return True, f"شهر لوکیشن تغییر کرد: {locked_city} ⟵ {cur_city or cur_cc} ({cur_ip})"
    elif locked_cc and cur_cc.lower() != locked_cc.lower():
        return True, f"لوکیشن تغییر کرد: {locked_cc} ⟵ {cur_cc} ({cur_ip})"

    return False, ""
