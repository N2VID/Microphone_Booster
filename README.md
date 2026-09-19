# Microphone Booster

A lightweight Windows desktop app that takes your microphone input, processes it **in real time**, and plays it directly to your speakers with low latency.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d6) ![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab) ![DSP: numpy](https://img.shields.io/badge/DSP-numpy-4dabcf) ![](https://komarev.com/ghpvc/?username=N2VID&color=red)

> Also available in [فارسی](#فارسی)

## Features

- **Real-time DSP chain** inside the audio callback:
  1. High-pass filter (90 Hz) to remove rumble / DC bumps
  2. Boost gain + output volume
  3. Noise gate with expander (smooth gain ramp, no zipper noise)
  4. Voice activity detection (mutes silence, fully)
  5. Soft peak limiter to prevent clipping
- **Input level meter** — shows the real microphone loudness, even when the gate mutes the output
- **Bilingual UI (Persian/English)** — corner EN/FA button, Persian = RTL layout, English = LTR
- **Standalone EXE** — built with PyInstaller, no Python needed on the target machine

## Requirements

- Windows 10 / 11
- Python 3.12 (only to run from source; the built EXE needs nothing)

Run from source:

```bash
pip install numpy sounddevice pystray Pillow pyinstaller
python mic_monitor.py
```

## Usage

1. Launch `Microphone Booster.exe` (or `python mic_monitor.py`).
2. Pick the microphone and the speaker device.
3. Adjust **Boost** and **Noise Gate Threshold**, turn on the gate / voice-detect checkboxes if you want silent gaps muted.
4. Close-to-tray keeps it running in the background; quit from the tray menu.

The tray icon menu shows the current input/output and lets you show/hide the window, run the speaker test, and quit.

> [!IMPORTANT]
> **Note:** To use Microphone Booster system-wide, a virtual audio device **must be installed**. We recommend [VB-CABLE](https://vb-audio.com/Cable/).
> Set your speaker output to **CABLE Input** and select **CABLE Output** as the microphone in the app.

## Build the EXE

```bash
pyinstaller --noconfirm --onefile --windowed --name "Microphone Booster" --icon icon.ico --add-data "icon.ico;." mic_monitor.py
```

Output: `dist/Microphone Booster.exe`

## Configuration

Settings (devices, boosts, checkbox states, language) persist to `%APPDATA%\Microphone Booster\config.json`. The log lives alongside it under `logs\`.

## License

Free to use. Made by **N2VID**.

---

## فارسی

# تقویت‌کننده میکروفون (Microphone Booster)

اپلیکیشن سبک ویندوزی که صدای میکروفون شما را **بدون تاخیر** پردازش می‌کند و مستقیم با تاخیر کم روی بلندگو پخش می‌کند.

## امکانات

- **پردازش صدای بدون تاخیر** داخل callback صدا:
  1. فیلتر بالاگذر (۹۰ هرتز) برای حذف صدای بم / نویز پایه
  2. افزودنی تقویت صدا و حجم خروجی
  3. نویزگیر با گسترش‌دهنده (شیب نرمِ صدا، بدون نویز زیپری)
  4. تشخیص صدا (قطع کامل در سکوت)
  5. محدودکننده نرم برای جلوگیری از کلیپینگ
- **نوار میزان ورودی** — بلندی واقعی میکروفون را نشان می‌دهد حتی وقتی نویزگیر خروجی را قطع کرده
- **رابط دوزبانه (فارسی/انگلیسی)** — دکمه‌ی EN/FA؛ فارسی = راست‌چین، انگلیسی = چپ‌چین
- **EXE مستقل** — ساخته‌شده با PyInstaller؛ بدون نیاز به نصب پایتون روی دستگاه

## طرز استفاده

1. `Microphone Booster.exe` را اجرا کنید (یا `python mic_monitor.py`).
2. دستگاه میکروفون و بلندگو را انتخاب کنید.
3. «تقویت صدا» و «آستانه نویزگیر» را تنظیم کنید؛ برای قطع سکوت، چک‌باکس‌های نویزگیر/تشخیص صدا را روشن کنید.
4. بستن پنجره برنامه را در نوار وظیفه نگه می‌دارد؛ خروج واقعی از منوی نوار وظیفه.

> [!IMPORTANT]
> **توجه:** برای استفاده از تقویت‌کننده میکروفون در سیستم حتما باید Virtual Audio نصب باشد و برای پیشنهاد می‌توانید از [VB-CABLE](https://vb-audio.com/Cable/) استفاده کنید.
> باید خروجی بلندگو را روی **CABLE Input** قرار دهید و در نرم افزار میکروفون **CABLE Output** انتخاب شود

## ساخت EXE

```bash
pyinstaller --noconfirm --onefile --windowed --name "Microphone Booster" --icon icon.ico --add-data "icon.ico;." mic_monitor.py
```

خروجی: `dist/Microphone Booster.exe`

## پیکربندی

تنظیمات (دستگاه‌ها، تقویت‌ها، حالت چک‌باکس‌ها، زبان) در `%APPDATA%\Microphone Booster\config.json` ذخیره می‌شود و لاگ کنار آن در پوشه‌ی `logs\` است.

## ساخته‌شده توسط

**N2VID**
