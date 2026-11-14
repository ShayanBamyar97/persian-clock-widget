<div dir="rtl">

# 🐧 راهنمای نصب و اجرا در لینوکس — ویجت ساعت تهران، تقویم شمسی و آلارم

**طراحی و توسعه:** شایان بامیار (`® Shayan Bamyar`)

این راهنما نحوه نصب، اجرا، فعال‌سازی اجرای خودکار (Startup) و حذف برنامه **Persian Clock & Calendar** را روی تمام توزیع‌های لینوکس توضیح می‌دهد.

---

## 📦 روش ۱: نصب روی اوبونتو، دبیان، مینت و Pop!_OS (فایل `.deb`) — پیشنهادی

فایل **[`release/linux/persian-clock-widget_1.0.0_all.deb`](release/linux/persian-clock-widget_1.0.0_all.deb)** را دانلود کنید و با **دابل‌کلیک** یا از طریق ترمینال نصب کنید:

```bash
sudo apt update
sudo apt install ./persian-clock-widget_1.0.0_all.deb
```

**کارهایی که این بسته خودکار انجام می‌دهد:**
- نصب پیش‌نیاز `python3-tk` (در صورت نبودن)
- نصب برنامه در `/opt/persian-clock-widget`
- نصب فونت‌های فارسی (`Vazir`, `B Yekan+`, `Iranian Sans`) و به‌روزرسانی `fc-cache`
- ساخت آیکون و میانبر در منوی برنامه‌ها (**Applications Menu**) با نام `Persian Clock & Calendar`
- ایجاد دستور ترمینال `persian-clock-widget`

**اجرا پس از نصب:**
- از منوی برنامه‌های سیستم روی **Persian Clock & Calendar** کلیک کنید، یا در ترمینال بزنید:
```bash
persian-clock-widget
```

---

## 🚀 روش ۲: نصب‌کننده تک‌فایلی روی تمام توزیع‌های لینوکس (`.sh`)

مناسب برای **Ubuntu, Debian, Arch, Manjaro, Fedora, openSUSE** و هر توزیع دیگر؛ فقط فایل **[`release/linux/PersianClockWidget-Linux-Installer.sh`](release/linux/PersianClockWidget-Linux-Installer.sh)** را اجرا کنید:

```bash
bash PersianClockWidget-Linux-Installer.sh
```

**کارهایی که نصب‌کننده انجام می‌دهد:**
1. بررسی وجود `python3` و `tkinter`
2. استخراج برنامه در `~/.local/share/persian-clock-widget`
3. نصب فونت‌های فارسی در `~/.local/share/fonts/PersianClockWidget`
4. ساخت میانبر منوی برنامه‌ها و فعال‌سازی اجرای خودکار با شروع لینوکس (`~/.config/autostart/persian-clock-widget.desktop`)
5. اجرای فوری ویجت

---

## 📁 روش ۳: اجرای پرتابل بدون نصب (از سورس یا آرشیو `tar.gz`)

اگر فایل **[`release/linux/PersianClockWidget-linux-portable.tar.gz`](release/linux/PersianClockWidget-linux-portable.tar.gz)** را دارید:

```bash
tar -xzf PersianClockWidget-linux-portable.tar.gz
cd persian-clock-widget
./scripts/run_linux.sh
```

### پیش‌نیازها (در صورت اجرای مستقیم از سورس):
- **Ubuntu / Debian / Mint:**
  ```bash
  sudo apt install python3 python3-tk mpv
  ```
- **Fedora:**
  ```bash
  sudo dnf install python3 python3-tkinter mpv
  ```
- **Arch / Manjaro:**
  ```bash
  sudo pacman -S python tk mpv
  ```
> **نکته صوتی:** برای پخش صدای MP3 آلارم‌ها در لینوکس، کافی است یکی از پخش‌کننده‌های سبک `mpv`، `ffmpeg` (`ffplay`)، `mpg123` یا `vlc` (`cvlc`) روی سیستم نصب باشد.

---

## 🔨 ساخت فایل اجرایی تک‌فایلی بومی لینوکس (اختیاری)

اگر می‌خواهید یک فایل اجرایی باینری تک‌فایلی (`ELF`) مخصوص سیستم خود بسازید:

```bash
./scripts/build_linux.sh
```
خروجی در مسیر `release/PersianClockWidget-linux` و `release/PersianClockWidget-linux.tar.gz` ساخته می‌شود.

---

## ⚙️ اجرای خودکار با بالا آمدن لینوکس (`Startup`)

برای فعال یا غیرفعال کردن اجرای خودکار برنامه هنگام روشن شدن سیستم:
1. روی آیکون **`⚙` (تنظیمات)** در ویجت کلیک کنید و تیک **«🚀 اجرا خودکار ویجت هم‌زمان با بالا آمدن لینوکس (Startup)»** را بزنید؛ **یا**
2. روی ویجت **راست‌کلیک** کرده و گزینه **«🚀 اجرا خودکار با شروع لینوکس»** را بزنید.

> فایل تنظیمات اتواستارت در مسیر `~/.config/autostart/persian-clock-widget.desktop` ساخته می‌شود.

---

## 📂 مسیر ذخیره تنظیمات، آلارم‌ها و مناسبت‌های شخصی

- در نصب سیستمی (`.deb`) یا اجرای باینری، اطلاعات کاربر (تنظیمات، آلارم‌ها و تولدهای ثبت‌شده) بدون نیاز به دسترسی `root` در مسیر زیر ذخیره می‌شوند:
  ```text
  ~/.local/share/PersianClockWidget/data/
  ├── config.json
  ├── alarms.json
  └── custom_occasions.json
  ```
- در اجرای پرتابل از پوشه پروژه، داده‌ها در پوشه `data/` کنار برنامه ذخیره می‌شوند.

---

## 🗑 حذف برنامه (`Uninstall`)

- **اگر با `.deb` نصب کرده‌اید:**
  ```bash
  sudo apt remove persian-clock-widget
  ```
- **اگر با `.sh` نصب کرده‌اید:**
  ```bash
  rm -rf ~/.local/share/persian-clock-widget \
         ~/.local/bin/persian-clock-widget \
         ~/.local/share/applications/persian-clock-widget.desktop \
         ~/.config/autostart/persian-clock-widget.desktop \
         ~/.local/share/fonts/PersianClockWidget
  ```

</div>
