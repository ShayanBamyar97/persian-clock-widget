# -*- coding: utf-8 -*-
"""
ماژول کاملا آفلاین تبدیل تاریخ شمسی، قمری و میلادی به همراه دیتابیس مناسبت‌ها و تعطیلات رسمی ایران
شامل محاسبه تقویم ماهانه، کبیسه شمسی و استخراج مناسبت‌های هر روز از هر ماه
"""

from datetime import datetime, date, timezone, timedelta
import json
import os

# منطقه زمانی تهران (UTC+03:30 ثابت)
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30), name="Asia/Tehran")

PERSIAN_WEEKDAYS = [
    "دوشنبه",     # Monday (0)
    "سه‌شنبه",    # Tuesday (1)
    "چهارشنبه",   # Wednesday (2)
    "پنج‌شنبه",   # Thursday (3)
    "جمعه",       # Friday (4)
    "شنبه",       # Saturday (5)
    "یک‌شنبه",    # Sunday (6)
]

# ترتیب روزهای هفته در تقویم ایرانی (از شنبه تا جمعه)
PERSIAN_WEEK_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"]

PERSIAN_MONTHS = [
    "",
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل دقیق تاریخ میلادی به هجری شمسی (جلالی)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        (365 * gy)
        + int((gy2 + 3) / 4)
        - int((gy2 + 99) / 100)
        + int((gy2 + 399) / 400)
        - 80
        + gd
        + g_d_m[gm - 1]
    )
    jy += 33 * int(days / 12053)
    days %= 12053
    jy += 4 * int(days / 1461)
    days %= 1461
    if days > 365:
        jy += int((days - 1) / 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + int(days / 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + int((days - 186) / 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """تبدیل دقیق تاریخ هجری شمسی (جلالی) به میلادی"""
    jy += 1595
    days = -355668 + (365 * jy) + (int(jy / 33) * 8) + int(((jy % 33) + 3) / 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * int(days / 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * int(days / 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * int(days / 1461)
    days %= 1461
    if days > 365:
        gy += int((days - 1) / 365)
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [
        0,
        31,
        29 if ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd


def is_jalali_leap(jy: int) -> bool:
    """بررسی کبیسه بودن سال شمسی"""
    # اگر روز 30 اسفند به تاریخ اول فروردین سال بعد تبدیل نشود، سال کبیسه است
    gy, gm, gd = jalali_to_gregorian(jy, 12, 30)
    jy2, jm2, jd2 = gregorian_to_jalali(gy, gm, gd)
    return (jy2 == jy and jm2 == 12 and jd2 == 30)


def get_jalali_month_days(jy: int, jm: int) -> int:
    """تعداد روزهای ماه شمسی"""
    if 1 <= jm <= 6:
        return 31
    elif 7 <= jm <= 11:
        return 30
    elif jm == 12:
        return 30 if is_jalali_leap(jy) else 29
    return 30


def gregorian_to_hijri(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به هجری قمری"""
    if gm < 3:
        gy -= 1
        gm += 12
    a = int(gy / 100)
    b = 2 - a + int(a / 4)
    jd = int(365.25 * (gy + 4716)) + int(30.6001 * (gm + 1)) + gd + b - 1524

    i_year = 10631.0 / 30.0
    epoch_astro = 1948084
    shift1 = 8.01 / 60.0

    z = jd - epoch_astro
    cyc = int(z / 10631.0)
    z = z - 10631 * cyc
    j = int((z - shift1) / i_year)
    iy = 30 * cyc + j
    z = z - int(j * i_year + shift1)
    im = int((z + 28.5001) / 29.5)
    if im == 13:
        im = 12
    id_day = z - int(29.5001 * im - 29)
    return int(iy), int(im), int(id_day)


# ---------------------------------------------------------------------------
# دیتابیس جامع مناسبت‌های شمسی ایران
# فرمت: (ماه, روز): [(عنوان مناسبت, آیا_تعطیل_رسمی_است؟), ...]
# ---------------------------------------------------------------------------
SHAMSI_OCCASIONS: dict[tuple[int, int], list[tuple[str, bool]]] = {
    # فروردین
    (1, 1): [("جشن نوروز و آغاز سال نو", True)],
    (1, 2): [("عید نوروز", True)],
    (1, 3): [("عید نوروز", True)],
    (1, 4): [("عید نوروز", True)],
    (1, 6): [("روز امید و زادروز زرتشت", False)],
    (1, 7): [("روز جهانی تئاتر", False)],
    (1, 10): [("جشن آبان‌گاه", False)],
    (1, 12): [("روز جمهوری اسلامی ایران", True)],
    (1, 13): [("جشن سیزده‌به‌در (روز طبیعت)", True)],
    (1, 18): [("روز جهانی بهداشت و سلامتی", False)],
    (1, 19): [("فروردین‌گان", False)],
    (1, 20): [("روز ملی فناوری هسته‌ای", False)],
    (1, 25): [("روز بزرگداشت عطار نیشابوری", False)],
    (1, 29): [("روز ارتش جمهوری اسلامی ایران", False)],

    # اردیبهشت
    (2, 1): [("روز بزرگداشت سعدی", False)],
    (2, 2): [("روز زمین پاک", False)],
    (2, 3): [("روز بزرگداشت شیخ بهایی / روز معماری", False)],
    (2, 7): [("روز ایمنی حمل و نقل", False)],
    (2, 9): [("روز شوراها / روز روان‌شناس و مشاور", False)],
    (2, 10): [("روز ملی خلیج فارس", False)],
    (2, 12): [("روز معلم", False)],
    (2, 15): [("روز بزرگداشت شیخ صدوق / جشن میانه بهار", False)],
    (2, 18): [("روز جهانی صلیب سرخ و هلال احمر", False)],
    (2, 25): [("روز پاسداشت زبان فارسی و بزرگداشت فردوسی", False)],
    (2, 27): [("روز ارتباطات و روابط عمومی", False)],
    (2, 28): [("روز بزرگداشت حکیم عمر خیام", False)],

    # خرداد
    (3, 1): [("روز بهره‌وری و بهینه‌سازی مصرف / بزرگداشت ملاصدرا", False)],
    (3, 3): [("سالروز آزادسازی خرمشهر", False)],
    (3, 4): [("روز دزفول (مقاومت و پایداری)", False)],
    (3, 6): [("جشن خردادگان", False)],
    (3, 14): [("رحلت امام خمینی", True)],
    (3, 15): [("قیام 15 خرداد", True)],
    (3, 16): [("روز جهانی محیط زیست", False)],
    (3, 20): [("روز جهانی صنایع دستی و فرش", False)],
    (3, 25): [("روز ملی گل و گیاه", False)],
    (3, 27): [("روز جهاد کشاورزی", False)],
    (3, 31): [("سالروز شهادت دکتر مصطفی چمران", False)],

    # تیر
    (4, 1): [("جشن آب‌پاشونک / روز اصناف", False)],
    (4, 5): [("روز جهانی مبارزه با مواد مخدر", False)],
    (4, 7): [("سالروز فاجعه هفتم تیر / روز قوه قضاییه", False)],
    (4, 8): [("روز مبارزه با سلاح‌های شیمیایی و میکروبی", False)],
    (4, 10): [("روز صنعت و معدن", False)],
    (4, 13): [("جشن تیرگان و بزرگداشت آرش کمانگیر", False)],
    (4, 14): [("روز قلم", False)],
    (4, 16): [("روز مالیات", False)],
    (4, 18): [("روز ادبیات کودکان و نوجوانان", False)],
    (4, 23): [("روز گفت‌وگو و تعامل سازنده با جهان", False)],
    (4, 25): [("روز بهزیستی و تامین اجتماعی", False)],
    (4, 27): [("اعلام پذیرش قطعنامه 598 شورای امنیت", False)],

    # مرداد
    (5, 6): [("روز ترویج آموزش‌های فنی و حرفه‌ای", False)],
    (5, 7): [("جشن امردادگان", False)],
    (5, 8): [("روز بزرگداشت شیخ شهاب‌الدین سهروردی", False)],
    (5, 9): [("روز اهدای خون", False)],
    (5, 10): [("جشن چله تابستان", False)],
    (5, 14): [("سالروز صدور فرمان مشروطیت", False)],
    (5, 17): [("روز خبرنگار", False)],
    (5, 22): [("روز تشکل‌ها و مشارکت‌های اجتماعی", False)],
    (5, 26): [("سالروز ورود آزادگان به میهن", False)],
    (5, 28): [("سالروز کودتای 28 مرداد", False)],
    (5, 30): [("روز بزرگداشت علامه مجلسی", False)],

    # شهریور
    (6, 1): [("روز بزرگداشت ابوعلی سینا و روز پزشک", False)],
    (6, 2): [("آغاز هفته دولت", False)],
    (6, 4): [("جشن شهریورگان / روز کارمند", False)],
    (6, 5): [("روز بزرگداشت محمد بن زکریای رازی و روز داروساز", False)],
    (6, 8): [("روز مبارزه با تروریسم", False)],
    (6, 11): [("روز صنعت چاپ", False)],
    (6, 12): [("روز مبارزه با استعمار انگلیس (شهادت رئیس‌علی دلواری)", False)],
    (6, 13): [("روز بزرگداشت ابوریحان بیرونی / روز تعاون", False)],
    (6, 17): [("قیام 17 شهریور", False)],
    (6, 21): [("روز سینما", False)],
    (6, 27): [("روز شعر و ادب فارسی و بزرگداشت استاد شهریار", False)],
    (6, 30): [("روز گفت‌وگوی تمدن‌ها", False)],
    (6, 31): [("آغاز هفته دفاع مقدس", False)],

    # مهر
    (7, 1): [("آغاز سال تحصیلی و فصل پاییز", False)],
    (7, 5): [("روز جهانی جهانگردی", False)],
    (7, 7): [("روز آتش‌نشانی و ایمنی / بزرگداشت شمس تبریزی", False)],
    (7, 8): [("روز بزرگداشت مولوی", False)],
    (7, 9): [("روز همبستگی با کودکان و نوجوانان فلسطینی", False)],
    (7, 10): [("جشن مهرگان", False)],
    (7, 13): [("روز نیروی انتظامی", False)],
    (7, 14): [("روز دامپزشکی", False)],
    (7, 15): [("روز روستا و عشایر", False)],
    (7, 16): [("روز جهانی کودک", False)],
    (7, 17): [("روز جهانی پست", False)],
    (7, 20): [("روز بزرگداشت حافظ شیرازی", False)],
    (7, 21): [("جشن رام‌روز", False)],
    (7, 24): [("روز ملی پارالمپیک", False)],
    (7, 26): [("روز تربیت بدنی و ورزش", False)],
    (7, 29): [("روز ملی کوهنورد", False)],

    # آبان
    (8, 1): [("روز آمار و برنامه‌ریزی", False)],
    (8, 7): [("روز بزرگداشت کوروش بزرگ", False)],
    (8, 8): [("روز نوجوان", False)],
    (8, 10): [("جشن آبانگان", False)],
    (8, 13): [("روز دانش‌آموز", False)],
    (8, 14): [("روز فرهنگ عمومی", False)],
    (8, 18): [("روز ملی کیفیت", False)],
    (8, 24): [("روز کتاب و کتاب‌خوانی", False)],

    # آذر
    (9, 1): [("آغاز ماه آذر", False)],
    (9, 5): [("روز بسیج مستضعفان", False)],
    (9, 7): [("روز نیروی دریایی", False)],
    (9, 9): [("جشن آذرگان", False)],
    (9, 10): [("روز مجلس", False)],
    (9, 13): [("روز بیمه", False)],
    (9, 15): [("روز حسابدار", False)],
    (9, 16): [("روز دانشجو", False)],
    (9, 25): [("روز پژوهش", False)],
    (9, 26): [("روز حمل و نقل و رانندگان", False)],
    (9, 30): [("جشن شب یلدا (شب چله)", False)],

    # دی
    (10, 1): [("روز میلاد خورشید و آغاز فصل زمستان", False)],
    (10, 4): [("جشن کریسمس", False)],
    (10, 5): [("روز ملی ایمنی در برابر زلزله", False)],
    (10, 7): [("سالروز تشکیل نهضت سوادآموزی", False)],
    (10, 8): [("روز صنعت پتروشیمی", False)],
    (10, 11): [("آغاز سال نو میلادی", False)],
    (10, 13): [("سالروز شهادت سردار قاسم سلیمانی", False)],
    (10, 15): [("جشن دی‌گان", False)],
    (10, 20): [("سالروز قتل امیرکبیر", False)],
    (10, 29): [("روز غزه", False)],

    # بهمن
    (11, 1): [("زادروز فردوسی", False)],
    (11, 2): [("جشن بهمنگان", False)],
    (11, 10): [("جشن سده", False)],
    (11, 12): [("بازگشت امام خمینی به ایران و آغاز دهه فجر", False)],
    (11, 14): [("روز فناوری فضایی", False)],
    (11, 19): [("روز نیروی هوایی", False)],
    (11, 22): [("پیروزی انقلاب اسلامی ایران", True)],
    (11, 29): [("جشن سپندارمذگان (روز عشق ایرانی)", False)],

    # اسفند
    (12, 5): [("روز بزرگداشت خواجه نصیرالدین طوسی و روز مهندس", False)],
    (12, 7): [("سالروز استقلال کانون وکلا و روز وکیل مدافع", False)],
    (12, 8): [("روز امور تربیتی و تربیت اسلامی", False)],
    (12, 14): [("روز احسان و نیکوکاری", False)],
    (12, 15): [("روز درختکاری", False)],
    (12, 18): [("روز جهانی زنان", False)],
    (12, 25): [("روز بزرگداشت پروین اعتصامی", False)],
    (12, 29): [("روز ملی شدن صنعت نفت ایران", True)],
    (12, 30): [("آخرین روز سال (کبیسه)", True)],
}

# ---------------------------------------------------------------------------
# مناسبت‌ها و تعطیلات رسمی قمری ایران
# ---------------------------------------------------------------------------
HIJRI_OCCASIONS: dict[tuple[int, int], list[tuple[str, bool]]] = {
    (1, 1): [("آغاز سال نو هجری قمری", False)],
    (1, 9): [("تاسوعای حسینی", True)],
    (1, 10): [("عاشورای حسینی", True)],
    (1, 12): [("شهادت امام زین‌العابدین (ع)", False)],
    (2, 20): [("اربعین حسینی", True)],
    (2, 28): [("رحلت پیامبر اکرم (ص) و شهادت امام حسن مجتبی (ع)", True)],
    (2, 30): [("شهادت امام رضا (ع)", True)],
    (3, 8): [("شهادت امام حسن عسکری (ع) و آغاز امامت حضرت ولی‌عصر (عج)", True)],
    (3, 12): [("آغاز هفته وحدت", False)],
    (3, 17): [("میلاد پیامبر اکرم (ص) و امام جعفر صادق (ع)", True)],
    (4, 8): [("ولادت امام حسن عسکری (ع)", False)],
    (5, 5): [("ولادت حضرت زینب (س) و روز پرستار", False)],
    (6, 3): [("شهادت حضرت فاطمه زهرا (س)", True)],
    (6, 20): [("ولادت حضرت فاطمه زهرا (س) و روز مادر", False)],
    (7, 1): [("ولادت امام محمد باقر (ع)", False)],
    (7, 3): [("شهادت امام علی النقی الهادی (ع)", False)],
    (7, 10): [("ولادت امام محمد تقی (ع)", False)],
    (7, 13): [("ولادت امام علی (ع) و روز پدر", True)],
    (7, 15): [("وفات حضرت زینب (س)", False)],
    (7, 25): [("شهادت امام موسی کاظم (ع)", False)],
    (7, 27): [("مبعث پیامبر اکرم (ص)", True)],
    (8, 3): [("ولادت امام حسین (ع) و روز پاسدار", False)],
    (8, 4): [("ولادت حضرت ابوالفضل العباس (ع) و روز جانباز", False)],
    (8, 5): [("ولادت امام زین‌العابدین (ع)", False)],
    (8, 11): [("ولادت حضرت علی‌اکبر (ع) و روز جوان", False)],
    (8, 15): [("نیمه شعبان؛ ولادت حضرت قائم (عج)", True)],
    (9, 15): [("ولادت امام حسن مجتبی (ع)", False)],
    (9, 19): [("شب قدر (ضربت خوردن امام علی ع)", False)],
    (9, 21): [("شهادت حضرت علی (ع)", True)],
    (9, 23): [("شب قدر", False)],
    (10, 1): [("عید سعید فطر", True)],
    (10, 2): [("تعطیل به مناسبت عید سعید فطر", True)],
    (10, 25): [("شهادت امام جعفر صادق (ع)", True)],
    (11, 1): [("ولادت حضرت معصومه (س) و روز دختر", False)],
    (11, 11): [("ولادت امام رضا (ع)", False)],
    (11, 30): [("شهادت امام محمد تقی (ع)", False)],
    (12, 1): [("سالروز ازدواج امام علی (ع) و حضرت فاطمه (س)", False)],
    (12, 7): [("شهادت امام محمد باقر (ع)", False)],
    (12, 9): [("روز عرفه", False)],
    (12, 10): [("عید سعید قربان", True)],
    (12, 15): [("ولادت امام علی النقی الهادی (ع)", False)],
    (12, 18): [("عید سعید غدیر خم", True)],
    (12, 20): [("ولادت امام موسی کاظم (ع)", False)],
}


def get_tehran_now() -> datetime:
    """دریافت زمان فعلی به وقت تهران (UTC+03:30)"""
    return datetime.now(TEHRAN_TZ)


def _load_custom_occasions(custom_occasions_path: str | None) -> dict:
    if custom_occasions_path and os.path.exists(custom_occasions_path):
        try:
            with open(custom_occasions_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_day_details(
    jy: int,
    jm: int,
    jd: int,
    custom_data: dict | None = None,
) -> dict:
    """دریافت اطلاعات و مناسبت‌های یک روز مشخص شمسی"""
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    hy, hm, hd = gregorian_to_hijri(gy, gm, gd)

    g_date = date(gy, gm, gd)
    weekday_idx = g_date.weekday()  # Monday=0 ... Sunday=6
    # تبدیل اندیس هفته میلادی به اندیس هفته ایرانی (شنبه=0 تا جمعه=6)
    persian_week_idx = (weekday_idx + 2) % 7
    weekday_name = PERSIAN_WEEKDAYS[weekday_idx]
    month_name = PERSIAN_MONTHS[jm]

    is_friday = (weekday_idx == 4)
    is_holiday = is_friday

    events: list[tuple[str, bool]] = []

    # 1. مناسبت‌های شمسی
    if (jm, jd) in SHAMSI_OCCASIONS:
        for title, hol in SHAMSI_OCCASIONS[(jm, jd)]:
            events.append((title, hol))
            if hol:
                is_holiday = True

    # 2. مناسبت‌های قمری
    if (hm, hd) in HIJRI_OCCASIONS:
        for title, hol in HIJRI_OCCASIONS[(hm, hd)]:
            events.append((title, hol))
            if hol:
                is_holiday = True

    # 3. مناسبت‌های سفارشی
    if custom_data:
        key = f"{jm:02d}-{jd:02d}"
        if key in custom_data:
            for item in custom_data[key]:
                if isinstance(item, dict):
                    t = item.get("title", "")
                    h = bool(item.get("holiday", False))
                else:
                    t = str(item)
                    h = False
                if t:
                    events.append((t, h))
                    if h:
                        is_holiday = True

    # مرتب‌سازی: ابتدا تعطیلات رسمی
    events.sort(key=lambda x: (not x[1]))
    titles = [e[0] for e in events]
    primary_occasion = " | ".join(titles) if titles else ""

    return {
        "jy": jy,
        "jm": jm,
        "jd": jd,
        "gy": gy,
        "gm": gm,
        "gd": gd,
        "hy": hy,
        "hm": hm,
        "hd": hd,
        "weekday_idx": weekday_idx,
        "persian_week_idx": persian_week_idx,  # 0=شنبه ... 6=جمعه
        "weekday_name": weekday_name,
        "month_name": month_name,
        "date_text": f"{weekday_name} {jd} {month_name} {jy}",
        "date_numeric": f"{jy:04d}/{jm:02d}/{jd:02d}",
        "events": events,
        "occasion": primary_occasion,
        "has_occasion": len(events) > 0,
        "is_holiday": is_holiday,
        "is_friday": is_friday,
    }


def get_month_calendar(
    jy: int,
    jm: int,
    custom_occasions_path: str | None = None,
) -> dict:
    """
    تولید اطلاعات کامل یک ماه شمسی برای نمایش در جدول تقویم
    خروجی شامل لیست روزها، اندیس روز اول ماه در هفته (شنبه=0 تا جمعه=6) و مناسبت‌های هر روز
    """
    custom_data = _load_custom_occasions(custom_occasions_path)
    total_days = get_jalali_month_days(jy, jm)

    days_list = []
    for d in range(1, total_days + 1):
        days_list.append(get_day_details(jy, jm, d, custom_data))

    first_day_week_idx = days_list[0]["persian_week_idx"] if days_list else 0

    return {
        "jy": jy,
        "jm": jm,
        "month_name": PERSIAN_MONTHS[jm],
        "header_title": f"{PERSIAN_MONTHS[jm]} {jy}",
        "total_days": total_days,
        "first_day_week_idx": first_day_week_idx,
        "days": days_list,
    }


def get_today_info(custom_occasions_path: str | None = None) -> dict:
    """دریافت اطلاعات لحظه‌ای ساعت تهران و تاریخ و مناسبت امروز"""
    now = get_tehran_now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    custom_data = _load_custom_occasions(custom_occasions_path)
    info = get_day_details(jy, jm, jd, custom_data)
    info["time_str"] = f"{now.hour:02d}:{now.minute:02d}"
    info["hour"] = now.hour
    info["minute"] = now.minute
    info["second"] = now.second
    return info
