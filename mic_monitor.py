# -*- coding: utf-8 -*-
"""
تقویت‌کننده میکروفون (Microphone Booster) - پخش مستقیم میکروفون روی بلندگو با تاخیر کم و کیفیت بالا
امکانات: نویزگیر، تشخیص صدا، تقویت صدا، نوار وظیفه (System Tray)، رابط تیره،
زبان فارسی/انگلیسی (راست‌چین/چپ‌چین)، فیلتر دستگاه‌های غیرفعال، تست بلندگو،
اجرای تک‌نمونه (Single Instance)
"""

import ctypes
import json
import logging
import logging.handlers
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pystray
import sounddevice as sd
from PIL import Image, ImageDraw

APP_NAME = "Microphone Booster"
APP_TITLE = "Microphone Booster"

# --------------------------------------------------------------------------
# ترجمه‌ها
# --------------------------------------------------------------------------
UI_TEXT = {
    "app_title": ("تقویت‌کننده میکروفون", "Microphone Booster"),
    "mic_label": ("میکروفون (ورودی)", "Microphone (Input)"),
    "speaker_label": ("بلندگو (خروجی)", "Speaker (Output)"),
    "boost": ("تقویت صدا", "Voice Boost"),
    "gate": ("آستانه نویزگیر", "Noise Gate Threshold"),
    "volume": ("حجم خروجی", "Output Volume"),
    "gate_on": ("نویزگیر فعال باشد", "Noise Gate enabled"),
    "vad_on": ("حذف صدای اضافه هنگام سکوت (تشخیص صدا)",
               "Remove background noise in silence (Voice Detect)"),
    "meter_label": ("سطح صدا", "Sound Level"),
    "st_stopped": ("وضعیت: غیرفعال", "Status: Inactive"),
    "st_running": ("وضعیت: فعال — در حال پخش (تاخیر {ms} ms)",
                   "Status: Active — playing (latency {ms} ms)"),
    "voice_talk": ("وضعیت: صحبت در حال تشخیص است", "Status: Voice detected"),
    "voice_silent": ("وضعیت: سکوت (نویز حذف شد)", "Status: Silence (noise removed)"),
    "voice_silent_off": ("وضعیت: سکوت", "Status: Silence"),
    "voice_off": ("وضعیت: —", "Status: —"),
    "btn_toggle_start": ("شروع پخش", "Start Playback"),
    "btn_toggle_stop": ("توقف پخش", "Stop Playback"),
    "btn_tray": ("پنهان در نوار وظیفه", "Hide to Tray"),
    "btn_quit": ("خروج از برنامه", "Quit"),
    "btn_test": ("تست صدای بلندگو", "Speaker Test"),
    "btn_lang": ("EN", "FA"),
    "err_title": ("خطا", "Error"),
    "err_sound": ("خطای صوتی", "Audio error"),
    "already": (
            "نرم افزار Microphone Booster از قبل در حال اجرا است.\n"
        "از پنجره ی قبلی یا آیکون نوار وظیفه استفاده کنید.",
        "Microphone Booster is already running.\nUse the existing window or the tray icon.",
    ),
    "refreshing": ("در حال بروزرسانی لیست...", "Updating device list..."),
    "tip_about": ("راهنمایی", "Help"),
    "tip_lang": ("تغییر زبان", "Change language"),
    "tip_refresh": ("بروزرسانی لیست دستگاه‌ها", "Update device list"),
    "tip_gate": ("هرچی عدد به صفر نزدیک‌تر باشد صدای پس‌زمینه بیشتر حذف می‌شود",
                 "The closer the value is to zero, the more background noise is removed."),
    "about_text": (
        "برای استفاده از نرم افزار برای بوست میکروفون در سیستم حتما به نرم افزار میکروفون مجازی "
        "نیاز است که حتما یکبار نصب شود\n"
        "«برای راهنمایی بیشتر وارد گیت هاب نرم افزار بشوید»",
        "To use this app for boosting your microphone system-wide, a virtual microphone software "
        "must be installed once.\n"
        "\"For more guidance, visit the app's GitHub page.\"",
    ),
    "close": ("بستن", "Close"),
}


# --------------------------------------------------------------------------
# تنظیمات و ذخیره‌سازی
# --------------------------------------------------------------------------
def config_dir():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path():
    return os.path.join(config_dir(), "config.json")


DEFAULT_CFG = {
    "input": "",
    "output": "",
    "boost_db": 0.0,
    "gate_db": -45.0,
    "gate_on": True,
    "vad_on": True,
    "volume": 0.9,
    "lang": "fa",
}


def load_cfg():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CFG)
        merged.update(cfg)
        return merged
    except Exception as e:
        log_exc("load_cfg")
        return dict(DEFAULT_CFG)


def save_cfg(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception as e:
        log_exc("save_cfg")


LOG_DIR = None


def setup_logging():
    """راه‌اندازی فایل لاگ در %APPDATA%\\Microphone Booster\\logs"""
    global LOG_DIR
    try:
        LOG_DIR = os.path.join(config_dir(), "logs")
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "micmonitor.log"),
            maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(fh)
        log("logging started: " + os.path.join(LOG_DIR, "micmonitor.log"))
    except Exception:
        pass


def log(*parts):
    try:
        logging.getLogger("micmonitor").info(" ".join(str(p) for p in parts))
    except Exception:
        pass


def log_exc(tag):
    try:
        logging.getLogger("micmonitor").exception("!!! %s", tag)
    except Exception:
        pass


# --------------------------------------------------------------------------
# اجرای تک‌نمونه
# --------------------------------------------------------------------------
_MUTEX_HANDLE = None
_SHOW_EVENT_NAME = "Local\\MicrophoneBooster_ShowEvent"
_SINGLE_INSTANCE_MUTEX = "Local\\MicrophoneBooster_SingleInstance"


def acquire_single_instance():
    global _MUTEX_HANDLE
    try:
        _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_MUTEX)
        err = ctypes.windll.kernel32.GetLastError()
        if err == 183:  # ERROR_ALREADY_EXISTS → نمونه دیگری در حال اجراست
            _signal_show_existing()
            return False
        return True
    except Exception:
        return True  # اگر قفل ممکن نشد، اجازه اجرا بده


def _signal_show_existing():
    """به نمونه اول سیگنال می‌دهد پنجره/ترهای خود را نشان دهد (و خارج می‌شود)"""
    for _ in range(20):
        ev = ctypes.windll.kernel32.OpenEventW(0x0002, False, _SHOW_EVENT_NAME)  # EVENT_MODIFY_STATE
        if ev:
            try:
                ctypes.windll.kernel32.SetEvent(ev)
            finally:
                ctypes.windll.kernel32.CloseHandle(ev)
            return
        time.sleep(0.05)


# --------------------------------------------------------------------------
# فیلترهای ساده (بیکواد)
# --------------------------------------------------------------------------
class BiquadHighPass:
    """فیلتر بالاگذر مرتبه دو (باترورث) برای حذف صدای بم و لرزش"""

    def __init__(self, fs, cutoff=90.0, q=0.707):
        w0 = 2.0 * math.pi * cutoff / fs
        cosw = math.cos(w0)
        alpha = math.sin(w0) / (2.0 * q)
        a0 = 1.0 + alpha
        self.b0 = (1.0 + cosw) / 2.0 / a0
        self.b1 = -(1.0 + cosw) / a0
        self.b2 = (1.0 + cosw) / 2.0 / a0
        self.a1 = -2.0 * cosw / a0
        self.a2 = (1.0 - alpha) / a0
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, samples):
        n = samples.shape[0]
        out = np.empty(n, np.float32)
        x1, x2, y1, y2 = self.x1, self.x2, self.y1, self.y2
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        s = samples
        for i in range(n):
            x0 = s[i]
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            out[i] = y0
            x2 = x1
            x1 = x0
            y2 = y1
            y1 = y0
        self.x1, self.x2, self.y1, self.y2 = x1, x2, y1, y2
        return out


def make_ding(fs):
    """صدای کوتاه «دینگ» برای تست بلندگو"""
    dur = 0.30
    t = np.arange(0, dur, 1.0 / fs)
    env = np.exp(-t * 10.0)
    s = (0.5 * np.sin(2 * np.pi * 880.0 * t) +
         0.18 * np.sin(2 * np.pi * 1320.0 * t) +
         0.10 * np.sin(2 * np.pi * 1760.0 * t)) * env
    return s.astype(np.float32)


# --------------------------------------------------------------------------
# هسته پردازش صدا (نویزگیر + تشخیص صدا + تقویت)
# --------------------------------------------------------------------------
class AudioEngine:
    def __init__(self, fs=48000):
        self.fs = fs
        self.hp = BiquadHighPass(fs, cutoff=90.0, q=0.707)

        self.gate_on = True
        self.vad_on = True
        self.gate_threshold = 10 ** (DEFAULT_CFG["gate_db"] / 20.0)
        self.boost_db = 0.0
        self.volume = 0.9

        self._gain_smooth = 1.0
        self._lim_gain = 1.0
        self.in_level = 0.0

        self.level = 0.0
        self.voice_active = False
        self.latency_ms = None
        self.running = False

        self.ding = None
        self.ding_pos = 0

    def set_gate_db(self, db):
        self.gate_threshold = 10 ** (db / 20.0)

    def play_ding(self):
        self.ding = make_ding(self.fs)
        self.ding_pos = 0

    def process(self, indata):
        x_raw = np.ascontiguousarray(indata[:, 0], dtype=np.float32)
        x = self.hp.process(x_raw)

        # سطح واقعی میکروفون (بعد از حذف بم، قبل از تقویت) برای نوار وضعیت
        in_peak = float(np.max(np.abs(x))) if x.size else 0.0
        attack = 0.35
        release = 0.05
        if in_peak > self.in_level:
            self.in_level += (in_peak - self.in_level) * attack
        else:
            self.in_level += (in_peak - self.in_level) * release

        boost_gain = 10 ** (self.boost_db / 20.0)
        x = x * boost_gain * float(self.volume)

        # ۲) نویزگیر (حذف نویز) + تشخیص صدا (حذف صدای اضافه هنگام سکوت)
        # آستانه با همان سطحی سنجیده میشود که نوار دسیبل نشان میدهد (in_level)
        # تا برش دقیقاً روی خط سبز اتفاق بیفتد و تحت تأثیر تقویت نباشد.
        thr = self.gate_threshold
        env = self.in_level

        target = 1.0
        if self.gate_on:
            # نویزگیر: سیگنال‌های پایین‌تر از آستانه را تضعیف می‌کند
            if env >= thr:
                target = 1.0
            else:
                ratio = 2.0
                target = (env / max(thr, 1e-9)) ** ratio
                target = min(target, 1.0)
        if self.vad_on:
            # تشخیص صدا: هنگام سکوت (زیر آستانه) صدا کاملاً حذف می‌شود
            if env >= thr:
                target = min(target, 1.0)
            else:
                target = 0.0

        if self.gate_on or self.vad_on:
            if target >= self._gain_smooth:
                target_s = self._gain_smooth + (target - self._gain_smooth) * 0.30
            else:
                target_s = self._gain_smooth + (target - self._gain_smooth) * 0.04
            ramp = np.linspace(self._gain_smooth, target_s, x.shape[0], dtype=np.float32)
            x = x * ramp
            self._gain_smooth = target_s
        else:
            self._gain_smooth = 1.0

        self.voice_active = env >= thr

        # ۳) محدودکننده برای جلوگیری از کلیپ
        peak = float(np.max(np.abs(x))) if x.size else 0.0
        lim_thr = 0.951
        tgt = (lim_thr / peak) if peak > lim_thr else 1.0
        if tgt < self._lim_gain:
            self._lim_gain += (tgt - self._lim_gain) * 0.5
        else:
            self._lim_gain += (tgt - self._lim_gain) * 0.08
        x = x * self._lim_gain

        # ۴) میکس صدای تست بلندگو (دینگ)
        if self.ding is not None:
            n = min(self.ding.size - self.ding_pos, x.size)
            if n > 0:
                x[:n] += self.ding[self.ding_pos:self.ding_pos + n]
                self.ding_pos += n
                pk2 = float(np.max(np.abs(x))) if x.size else 0.0
                if pk2 > 0.951:
                    x *= 0.951 / pk2
            if self.ding_pos >= self.ding.size:
                self.ding = None

        if x.size:
            self.level = min(1.0, float(np.max(np.abs(x))) * 1.05)
        else:
            self.level = 0.0
        return x


# --------------------------------------------------------------------------
# انتخاب دستگاه‌های صوتی (فقط دستگاه‌های فعال)
# --------------------------------------------------------------------------
def active_endpoint_names():
    """نام دستگاه‌های صوتی فعال (Status=OK) از کلاس AudioEndpoint ویندوز"""
    if hasattr(active_endpoint_names, "_cache"):
        return active_endpoint_names._cache
    names = set()
    try:
        ps = ("Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
              "ForEach-Object { $_.Status + \"`t\" + $_.FriendlyName }")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=40)
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip().upper() == "OK":
                nm = parts[1].strip()
                if nm:
                    names.add(nm.lower())
        log("active endpoints found:", len(names))
    except Exception:
        log_exc("active_endpoint_names")
    if not names:
        log("WARNING: no active endpoints detected - falling back to unfiltered device list")
    active_endpoint_names._cache = names
    return names


def canonical_name(pname, active_names):
    """پیدا کردن نام کامل/اصلی دستگاه فعال که این نام PortAudio به آن تعلق دارد"""
    p = pname.strip().lower()
    if not p:
        return None
    if not active_names:
        return pname
    if p in active_names:
        return pname
    cands = [n for n in active_names if p.startswith(n) or n.startswith(p)]
    if not cands:
        return None
    best = max(cands, key=len)
    return best


def list_devices():
    active = active_endpoint_names()
    hostapis = sd.query_hostapis()
    wasapi_idx = next((i for i, h in enumerate(hostapis) if "wasapi" in h["name"].lower()), None)

    raw_in, raw_out = [], []
    for i, d in enumerate(sd.query_devices()):
        it = {"id": i, "name": d["name"], "hostapi": d["hostapi"]}
        if d["max_input_channels"] > 0:
            raw_in.append(it)
        if d["max_output_channels"] > 0:
            raw_out.append(it)

    def clean(items):
        best = {}
        for it in items:
            canon = canonical_name(it["name"], active)
            if canon is None:
                continue  # فقط دستگاه‌های فعال نشان داده می‌شوند
            key = canon.lower()
            if key in best:
                # ترجیح دستگاه WASAPI برای تاخیر کمتر
                if it["hostapi"] == wasapi_idx and best[key]["hostapi"] != wasapi_idx:
                    best[key] = dict(it, name=canon)
            else:
                best[key] = dict(it, name=canon)
        return list(best.values())

    inputs = clean(raw_in)
    outputs = clean(raw_out)
    log("device list filtered -> inputs:", len(inputs), "outputs:", len(outputs))
    for d in inputs:
        log("  input :", d["name"])
    for d in outputs:
        log("  output:", d["name"])
    return {
        "inputs": inputs,
        "outputs": outputs,
        "hostapis": hostapis,
    }


# --------------------------------------------------------------------------
# انتخاب پیش‌فرض دستگاه‌ها
# --------------------------------------------------------------------------
def score_dev(dev, prefer_names, wasapi_idx, default_id):
    s = 0
    if dev["hostapi"] == wasapi_idx:
        s += 3
    if dev["id"] == default_id:
        s += 2
    n = dev["name"].lower()
    for p in prefer_names:
        if p in n:
            s += 4
            break
    return s


def pick_default(devices, prefer_names, hostapis, is_input):
    wasapi_idx = None
    h_wasapi = None
    for hi, h in enumerate(hostapis):
        if "wasapi" in h["name"].lower():
            wasapi_idx = hi
            h_wasapi = h
            break
    default_id = None
    if h_wasapi is not None:
        default_id = h_wasapi["default_input_device"] if is_input else h_wasapi["default_output_device"]
    best, best_score = None, -1
    for dev in devices:
        sc = score_dev(dev, prefer_names, wasapi_idx, default_id)
        if sc > best_score:
            best_score, best = sc, dev
    return best


# --------------------------------------------------------------------------
# نرم‌افزار
# --------------------------------------------------------------------------
class SquareCheck:
    """چک‌باکس مربعی: تیک خورده = مربع پر، تیک نخورده = مربع توخالی"""

    def __init__(self, parent, text="", checked=False, on_toggle=None,
                 bg="#1e2024", fg="#e8e8ea", accent="#2563eb", outline="#6b7280"):
        self._checked = bool(checked)
        self.on_toggle = on_toggle
        self.frame = ttk.Frame(parent, style="TCard.TFrame")
        self.cv = tk.Canvas(self.frame, width=26, height=26, bg=bg,
                            highlightthickness=0, bd=0)
        self.lbl = ttk.Label(self.frame, text=text, style="Card.TLabel")
        self.cv.pack(side="left", padx=(2, 0))
        self.lbl.pack(side="left", padx=(8, 2))
        self.cv.bind("<Button-1>", self._click)
        self.lbl.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, event=None):
        self._checked = not self._checked
        self._draw()
        if self.on_toggle:
            try:
                self.on_toggle()
            except Exception:
                log_exc("SquareCheck.on_toggle")

    def _draw(self):
        self.cv.delete("all")
        if self._checked:
            self.cv.create_rectangle(3, 3, 23, 23, width=0, fill="#2563eb")
            self.cv.create_line(7, 13, 11, 17, 19, 8,
                                fill="#ffffff", width=2,
                                capstyle=tk.ROUND, joinstyle=tk.ROUND)
        else:
            self.cv.create_rectangle(3, 3, 23, 23, width=2,
                                     outline="#6b7280")

    def get(self):
        return self._checked

    def set(self, value):
        self._checked = bool(value)
        self._draw()

    def config(self, **kw):
        if "text" in kw:
            self.lbl.config(text=kw.pop("text"))
        if kw:
            self.lbl.config(**kw)

    def set_rtl(self, rtl):
        self.cv.pack_forget()
        self.lbl.pack_forget()
        if rtl:
            self.cv.pack(side="right", padx=(0, 2))
            self.lbl.pack(side="right", padx=(2, 8))
        else:
            self.cv.pack(side="left", padx=(2, 0))
            self.lbl.pack(side="left", padx=(8, 2))


class ToolTip:
    """نکته نمایشی (tooltip) ساده: با بردن موس روی ویجت، متن کنار موس ظاهر می‌شود"""

    def __init__(self, widget, text, root):
        self.widget = widget
        self.text = text
        self.root = root
        self._tip = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule_on_enter, add="+")
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def set_text(self, text):
        self.text = text

    def _schedule_on_enter(self, event=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.widget.after(500, self._show)

    def _show(self):
        self._after_id = None
        try:
            if self._tip is not None:
                self._tip.destroy()
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            lbl = ttk.Label(tip, text=self.text, style="Tip.TLabel")
            lbl.pack()
            tip.update_idletasks()
            x = self.widget.winfo_rootx() + 10
            # کادر نکته بالای ویجت نمایش داده میشود
            y = self.widget.winfo_rooty() - tip.winfo_height() - 6
            if y < 0:  # اگر بالا جا نبود، پایین ویجت بگذار
                y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            tip.wm_geometry(f"+{x}+{y}")
            self._tip = tip
        except Exception:
            pass

    def _hide(self, event=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.lang = "fa" if self.cfg.get("lang", "fa") not in ("en", "fa") else self.cfg.get("lang", "fa")
        self.engine = None
        self.stream = None
        self.cb_queue = queue.Queue(maxsize=8)
        self.icon = None
        self._voice_last = None

        self.devices = list_devices()
        self.wasapi_idx = next((i for i, h in enumerate(self.devices["hostapis"])
                                if "wasapi" in h["name"].lower()), None)
        log("App initialized; lang =", self.lang)

        self._static = []
        self._mirror_grid = []
        self._mirror_pack = []
        self._ready = False  # تا پایان بازیابی تنظیمات، ذخیره‌سازی اسلایدرها انجام نشود

        self._build_ui()
        self._setup_tray()
        self._restore_cfg()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.after(50, self._tick)
        self._restarting = False
        self._refreshing = False
        self._setup_show_event()

    # --------------------------------------------------------------- ترجمه
    def _t(self, key, **fmt):
        pair = UI_TEXT.get(key, ("?", "?"))
        s = pair[1] if self.lang == "en" else pair[0]
        if fmt:
            try:
                s = s.format(**fmt)
            except Exception:
                pass
        return s

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self._set_window_icon()
        root = self.root
        C_BG = "#17181b"
        C_CARD = "#1e2024"
        C_TEXT = "#e8e8ea"
        C_DIM = "#9a9aa2"
        C_ACCENT = "#3b82f6"
        C_ACCENT2 = "#2563eb"
        C_OK = "#22c55e"
        C_BAD = "#ef4444"

        root.title(self._t("app_title"))
        root.geometry("430x620")
        root.minsize(400, 560)
        root.configure(bg=C_BG)

        # استایل کلی
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=C_BG, foreground=C_TEXT,
                        troughcolor="#0c0c0e", fieldbackground=C_CARD,
                        bordercolor=C_CARD, font=("Segoe UI", 10))
        style.configure("TCard.TFrame", background=C_CARD)
        style.configure("TLabel", background=C_BG, foreground=C_TEXT)
        style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
        style.configure("Dim.TLabel", background=C_BG, foreground=C_DIM)
        style.configure("CardDim.TLabel", background=C_CARD, foreground=C_DIM)
        style.configure("Head.TLabel", background=C_BG, foreground=C_TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Accent.TLabel", background=C_CARD, foreground=C_ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("CardAccent.TLabel", background=C_CARD, foreground=C_ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background=C_ACCENT, foreground="#ffffff",
                        font=("Segoe UI", 11, "bold"), borderwidth=0, padding=(12, 8))
        style.map("Accent.TButton",
                  background=[("active", C_ACCENT2), ("disabled", "#3b3b3f")],
                  foreground=[("disabled", "#999")])
        style.configure("Ghost.TButton", background=C_CARD, foreground=C_TEXT,
                        borderwidth=0, padding=(10, 6))
        style.map("Ghost.TButton", background=[("active", "#2a2d33")])
        style.configure("Refresh.TButton", background="#2b2f36", foreground=C_TEXT,
                        borderwidth=0, padding=(10, 1), font=("Segoe UI", 13))
        style.map("Refresh.TButton",
                  background=[("active", "#353a42")],
                  foreground=[("active", C_TEXT)])
        style.configure("Tip.TLabel", background="#26292e", foreground="#e8e8ea",
                        borderwidth=1, relief="solid", bordercolor="#3a3f46",
                        padding=(7, 4))
        style.configure("TCheckbutton", background=C_CARD, foreground=C_TEXT)
        style.map("TCheckbutton", background=[("active", C_CARD)])
        style.configure("Horizontal.TScale", background=C_CARD, troughcolor="#0c0c0e")

        # کادر انتخاب دستگاه: پس‌زمینه مشکی و فونت سفید
        root.option_add("*TCombobox*Listbox.background", "#000000")
        root.option_add("*TCombobox*Listbox.foreground", "#ffffff")
        root.option_add("*TCombobox*Listbox.selectBackground", "#2563eb")
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        style.configure("DarkCombo.TCombobox",
                        fieldbackground=C_CARD, background=C_CARD,
                        foreground="#ffffff", arrowcolor="#ffffff", bordercolor=C_CARD)
        style.map("DarkCombo.TCombobox",
                  fieldbackground=[("readonly", C_CARD)],
                  selectbackground=[("readonly", C_CARD)],
                  selectforeground=[("readonly", "#ffffff")],
                  background=[("readonly", C_CARD)],
                  foreground=[("readonly", "#ffffff")])

        # --> سربرگ
        self.hdr = ttk.Frame(root, style="TCard.TFrame")
        self.hdr.pack(fill="x", padx=10, pady=(10, 4))
        self.hdr_title = ttk.Label(self.hdr, text=self._t("app_title"), style="Head.TLabel")
        self.hdr_lang = ttk.Button(self.hdr, style="Ghost.TButton", width=3, command=self.toggle_lang)
        self.hdr_lang.config(text=self._t("btn_lang"))
        self.btn_about = ttk.Button(self.hdr, style="Ghost.TButton", width=2, command=self._show_about)
        self.btn_about.config(text="?")
        self.lbl_status = ttk.Label(self.hdr, style="CardAccent.TLabel")
        self._static.append((self.hdr_title, "app_title"))

        # --> کارت دستگاه
        dev = ttk.Frame(root, style="TCard.TFrame")
        dev.pack(fill="x", padx=10, pady=4)
        self.dev_head = ttk.Frame(dev, style="TCard.TFrame")
        self.dev_head.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.lbl_mic = ttk.Label(self.dev_head, style="CardDim.TLabel")
        self.lbl_spk = ttk.Label(dev, style="CardDim.TLabel")
        self.lbl_spk.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 2))
        self.btn_refresh = ttk.Button(self.dev_head, style="Refresh.TButton", width=2,
                                      command=self._on_refresh_devices)
        self.btn_refresh.config(text="↻")
        self.lbl_upd = ttk.Label(dev, style="CardDim.TLabel")
        self.cb_in = ttk.Combobox(dev, width=38, state="readonly", style="DarkCombo.TCombobox")
        self.cb_out = ttk.Combobox(dev, width=38, state="readonly", style="DarkCombo.TCombobox")
        self.cb_in.grid(row=1, column=0, sticky="ew", padx=10)
        self.cb_out.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.cb_in.bind("<<ComboboxSelected>>", self._on_dev_change)
        self.cb_out.bind("<<ComboboxSelected>>", self._on_dev_change)
        dev.columnconfigure(0, weight=1)
        self._layout_dev_head()
        self._static.append((self.lbl_mic, "mic_label"))
        self._static.append((self.lbl_spk, "speaker_label"))
        self._mirror_grid.append(self.lbl_spk)

        # --> کارت تنظیمات
        settings = ttk.Frame(root, style="TCard.TFrame")
        settings.pack(fill="x", padx=10, pady=4)
        self.lbl_boost = ttk.Label(settings, style="CardDim.TLabel")
        self.lbl_gate = ttk.Label(settings, style="CardDim.TLabel")
        self.lbl_vol = ttk.Label(settings, style="CardDim.TLabel")
        self.lbl_boost.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.lbl_gate.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 0))
        self.lbl_vol.grid(row=4, column=0, sticky="ew", padx=10, pady=(8, 0))
        self.sc_boost = ttk.Scale(settings, from_=0, to=30, style="Horizontal.TScale",
                                  command=lambda v: self._on_boost(v))
        self.sc_gate = ttk.Scale(settings, from_=-60, to=-15, style="Horizontal.TScale",
                                 command=lambda v: self._on_gate(v))
        self.sc_vol = ttk.Scale(settings, from_=0, to=1, style="Horizontal.TScale",
                                command=lambda v: self._on_vol(v))
        self.sc_boost.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
        self.sc_gate.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10)
        self.sc_vol.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10)
        self.tip_gate = ToolTip(self.sc_gate, self._t("tip_gate"), root)
        self.chk_gate = SquareCheck(settings, on_toggle=self._on_checks)
        self.chk_vad = SquareCheck(settings, on_toggle=self._on_checks)
        self.chk_gate.frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
        self.chk_vad.frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        settings.columnconfigure(0, weight=1)
        self._static.append((self.lbl_boost, "boost"))
        self._static.append((self.lbl_gate, "gate"))
        self._static.append((self.lbl_vol, "volume"))
        self._static.append((self.chk_gate, "gate_on"))
        self._static.append((self.chk_vad, "vad_on"))
        self._mirror_grid.append(self.lbl_boost)
        self._mirror_grid.append(self.lbl_gate)
        self._mirror_grid.append(self.lbl_vol)

        # --> نشانگر سطح صدا
        meter_card = ttk.Frame(root, style="TCard.TFrame")
        meter_card.pack(fill="x", padx=10, pady=4)
        self.lbl_meter = ttk.Label(meter_card, style="CardDim.TLabel")
        self.lbl_meter.pack(fill="x", padx=10, pady=(10, 0))
        self.meter_cv = tk.Canvas(meter_card, height=18, bg="#0c0c0e", highlightthickness=0)
        self.meter_cv.pack(fill="x", padx=10)
        self.meter_rect = self.meter_cv.create_rectangle(0, 0, 0, 18, fill="#22c55e", outline="")
        # خط سبز نازک آستانه نویزگیر روی نوار دسیبل (جای آن بر اساس gate_db محاسبه می‌شود)
        self.meter_gate = self.meter_cv.create_line(0, 1, 0, 17, fill="#4ade80", width=2)
        self.lbl_voice = ttk.Label(meter_card, style="CardDim.TLabel")
        self.lbl_voice.pack(fill="x", padx=10, pady=(4, 10))
        self._static.append((self.lbl_meter, "meter_label"))
        self._mirror_pack.append(self.lbl_meter)
        self._mirror_pack.append(self.lbl_voice)

        # --> دکمه‌ها
        btns = ttk.Frame(root, style="TCard.TFrame")
        btns.pack(fill="x", padx=10, pady=4)
        self.btn_toggle = ttk.Button(btns, style="Accent.TButton", command=self.toggle_run)
        self.btn_tray = ttk.Button(btns, style="Ghost.TButton", command=self.hide_to_tray)
        self.btn_quit = ttk.Button(btns, style="Ghost.TButton", command=self.quit_app)
        self.btn_test = ttk.Button(btns, style="Ghost.TButton", command=self.test_sound)
        self.btn_toggle.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        self.btn_quit.grid(row=1, column=0, sticky="ew", padx=(10, 5), pady=(0, 6))
        self.btn_tray.grid(row=1, column=1, sticky="ew", padx=(5, 10), pady=(0, 6))
        self.btn_test.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        self._static.append((self.btn_toggle, "btn_toggle_start"))
        self._static.append((self.btn_tray, "btn_tray"))
        self._static.append((self.btn_quit, "btn_quit"))
        self._static.append((self.btn_test, "btn_test"))

        # فهرست دستگاه‌ها
        self.cb_in["values"] = [d["name"] for d in self.devices["inputs"]]
        self.cb_out["values"] = [d["name"] for d in self.devices["outputs"]]

        # نکته نمایشی (tooltip) برای دکمه‌ها
        self.tip_about = ToolTip(self.btn_about, self._t("tip_about"), root)
        self.tip_lang = ToolTip(self.hdr_lang,
                                "تغییر زبان" if self.lang == "en" else "Change Language", root)
        self.tip_refresh = ToolTip(self.btn_refresh, self._t("tip_refresh"), root)

        root.bind("<Escape>", lambda e: self.hide_to_tray())
        root.update_idletasks()

    def _btn_layout(self):
        rtl = self.lang == "fa"
        self.btn_toggle.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        if rtl:
            self.btn_tray.grid(row=1, column=0, sticky="ew", padx=(10, 5), pady=(0, 6))
            self.btn_quit.grid(row=1, column=1, sticky="ew", padx=(5, 10), pady=(0, 6))
        else:
            self.btn_quit.grid(row=1, column=0, sticky="ew", padx=(10, 5), pady=(0, 6))
            self.btn_tray.grid(row=1, column=1, sticky="ew", padx=(5, 10), pady=(0, 6))
        self.btn_test.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

    def _header_layout(self):
        rtl = self.lang == "fa"
        for w in (self.hdr_title, self.hdr_lang, self.btn_about):
            w.pack_forget()
        if rtl:
            self.hdr_lang.pack(side="right", padx=(10, 6), pady=(10, 2))
            self.btn_about.pack(side="right", padx=(0, 6), pady=(10, 2))
            self.hdr_title.pack(side="right", padx=(0, 6), pady=(10, 2))
        else:
            self.hdr_title.pack(side="left", padx=(12, 0), pady=(10, 2))
            self.btn_about.pack(side="right", padx=(0, 6), pady=(10, 2))
            self.hdr_lang.pack(side="right", padx=(0, 12), pady=(10, 2))
        self.lbl_status.pack_forget()
        self.lbl_status.pack(fill="x", anchor="e" if rtl else "w", padx=(12, 12), pady=(0, 10))

    def _apply_rtl(self):
        rtl = self.lang == "fa"
        anchor = "e" if rtl else "w"
        just = "right" if rtl else "left"
        for w in self._mirror_grid:
            w.configure(anchor=anchor, justify=just)
            w.grid(sticky="ew")
        for w in self._mirror_pack:
            w.configure(anchor=anchor, justify=just)
            w.pack(fill="x")
        self.chk_gate.set_rtl(rtl)
        self.chk_vad.set_rtl(rtl)
        self._layout_dev_head()

    def _layout_dev_head(self):
        # فارسی: دکمه رفرش بالا-چپ | انگلیسی: بالا-راست
        rtl = self.lang == "fa"
        for w in (self.lbl_mic, self.btn_refresh):
            w.pack_forget()
        self.lbl_mic.configure(anchor="e" if rtl else "w", justify="right" if rtl else "left")
        if rtl:
            self.btn_refresh.pack(side="left", padx=(10, 0), pady=(5, 0))
            self.lbl_mic.pack(side="left", fill="x", expand=True, padx=(4, 10), pady=(10, 2))
        else:
            self.lbl_mic.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=(10, 2))
            self.btn_refresh.pack(side="right", padx=(0, 10), pady=(5, 0))

    def _refresh_dynamic(self):
        db = float(self.cfg.get("boost_db", 0))
        gd = float(self.cfg.get("gate_db", -45))
        vol = float(self.cfg.get("volume", 0.9))
        if self.lang == "fa":
            t_boost = f"تقویت صدا: {db:.0f} دسیبل"
            t_gate = f"آستانه نویزگیر: {gd:.0f} دسیبل"
            t_vol = f"حجم خروجی: {vol * 100:.0f}٪"
        else:
            t_boost = f"Voice Boost: {db:.0f} dB"
            t_gate = f"Noise Gate Threshold: {gd:.0f} dB"
            t_vol = f"Output Volume: {vol * 100:.0f}%"
        self.lbl_boost.config(text=t_boost)
        self.lbl_gate.config(text=t_gate)
        self.lbl_vol.config(text=t_vol)

    def _refresh_status(self):
        running = bool(self.engine and self.engine.running)
        if running:
            ms = getattr(self.engine, "latency_ms", None)
            self.lbl_status.config(
                text=self._t("st_running", ms=int(round(ms)) if ms else 0),
                foreground="#22c55e")
        else:
            self.lbl_status.config(text=self._t("st_stopped"), foreground="#9a9aa2")

    def _refresh_ui(self):
        self.root.title(self._t("app_title"))
        for w, key in self._static:
            try:
                w.config(text=self._t(key))
            except Exception:
                pass
        self.hdr_lang.config(text=self._t("btn_lang"))
        self.tip_about.set_text(self._t("tip_about"))
        self.tip_gate.set_text(self._t("tip_gate"))
        # نکته دکمه زبان همیشه به زبانی است که فعلاً فعال نیست (زبان مقصد)
        self.tip_lang.set_text("تغییر زبان" if self.lang == "en" else "Change Language")
        self.tip_refresh.set_text(self._t("tip_refresh"))
        self.btn_toggle.config(
            text=self._t("btn_toggle_stop") if (self.engine and self.engine.running)
            else self._t("btn_toggle_start"))
        self._header_layout()
        self._btn_layout()
        self._apply_rtl()
        self._refresh_dynamic()
        self._refresh_status()

    def toggle_lang(self):
        self.lang = "en" if self.lang == "fa" else "fa"
        self.cfg["lang"] = self.lang
        save_cfg(self.cfg)
        self._refresh_ui()
        self._voice_last = None
        try:
            self.icon.menu = self._tray_menu()
            self.icon.update_menu()
        except Exception:
            pass

    def _restore_cfg(self):
        c = self.cfg
        in_names = [d["name"] for d in self.devices["inputs"]]
        out_names = [d["name"] for d in self.devices["outputs"]]
        if c["input"] in in_names:
            self.cb_in.set(c["input"])
        else:
            p = pick_default(self.devices["inputs"], ["microphone"],
                             self.devices["hostapis"], True)
            if p:
                self.cb_in.set(p["name"])
        if c["output"] in out_names:
            self.cb_out.set(c["output"])
        else:
            p = pick_default(self.devices["outputs"], ["headphones", "speakers", "speaker"],
                             self.devices["hostapis"], False)
            if p:
                self.cb_out.set(p["name"])

        self.sc_boost.set(c["boost_db"])
        self.sc_gate.set(c["gate_db"])
        self.sc_vol.set(c["volume"])
        self.chk_gate.set(bool(c.get("gate_on", False)))
        self.chk_vad.set(bool(c.get("vad_on", False)))
        self._refresh_dynamic()
        self._refresh_ui()
        self._ready = True  # بازیابی تمام شد؛ از این به بعد اسلایدرها ذخیره می‌کنند

    # ------------------------------------------------------ تغییر دستگاه‌ها
    def _on_dev_change(self, event=None):
        # وقتی ورودی/خروجی تغییر کرد: ذخیره کن و اگر پخش در حال اجراست دوباره راه‌اندازی شو
        if not self._ready:
            return
        self.cfg["input"] = self.cb_in.get()
        self.cfg["output"] = self.cb_out.get()
        self._save()
        changed = True
        self._request_restart(changed)

    def _on_refresh_devices(self):
        # رفرش لیست در یک ثرد جدا انجام میشود تا رابط کاربری فریز نشود
        if self._refreshing:
            return
        self._refreshing = True
        self.btn_refresh.config(state="disabled")
        self.lbl_upd.config(text=self._t("refreshing"))
        self.lbl_upd.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        threading.Thread(target=self._refresh_devices_worker, daemon=True).start()

    def _refresh_devices_worker(self):
        try:
            if hasattr(active_endpoint_names, "_cache"):
                del active_endpoint_names._cache
            devs = list_devices()
        except Exception:
            log_exc("_refresh_devices_worker")
            devs = None
        try:
            self.root.after(0, lambda: self._finish_refresh(devs))
        except Exception:
            pass

    def _finish_refresh(self, devs):
        # این تابع در نخ اصلی UI اجرا میشود
        self._refreshing = False
        self.btn_refresh.config(state="normal")
        self.lbl_upd.grid_remove()
        if devs is None:
            return
        try:
            self.devices = devs
            in_names = [d["name"] for d in devs["inputs"]]
            out_names = [d["name"] for d in devs["outputs"]]
            cur_in = self.cb_in.get()
            cur_out = self.cb_out.get()
            self.cb_in["values"] = in_names
            self.cb_out["values"] = out_names
            changed = False
            if cur_in not in in_names:
                p = pick_default(devs["inputs"], ["microphone"], devs["hostapis"], True)
                cur_in = p["name"] if p else (in_names[0] if in_names else "")
                changed = True
            if cur_out not in out_names:
                p = pick_default(devs["outputs"], ["headphones", "speakers", "speaker"],
                                 devs["hostapis"], False)
                cur_out = p["name"] if p else (out_names[0] if out_names else "")
                changed = True
            self.cb_in.set(cur_in)
            self.cb_out.set(cur_out)
            self.cfg["input"] = cur_in
            self.cfg["output"] = cur_out
            self._save()
            log("device list refreshed -> inputs:", len(in_names), "outputs:", len(out_names))
            self._request_restart(changed)
        except Exception:
            log_exc("_finish_refresh")

    def _request_restart(self, changed):
        # اگر تغییری واقعی شد و پخش فعال بود، یک بار stop/start بزن تا اعمال شود
        if not changed or self._restarting:
            return
        if not (self.engine and getattr(self.engine, "running", False)):
            return
        self._restarting = True
        threading.Thread(target=self._restart_worker, daemon=True).start()

    def _restart_worker(self):
        try:
            s = self.stream
            self.stream = None
            if self.engine:
                self.engine.running = False
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
            self._start_async()
        finally:
            self._restarting = False

    # ------------------------------------------------------------------ لغزنده‌ها
    def _on_boost(self, v):
        self.cfg["boost_db"] = float(v)
        if self.engine:
            self.engine.boost_db = float(v)
        self._refresh_dynamic()
        if self._ready:
            self._save()

    def _on_gate(self, v):
        self.cfg["gate_db"] = float(v)
        if self.engine:
            self.engine.set_gate_db(float(v))
        self._refresh_dynamic()
        if self._ready:
            self._save()

    def _on_checks(self):
        """اعمال فوری وضعیت چکباکسها (حتی هنگام اجرا)"""
        self.cfg["gate_on"] = self.chk_gate.get()
        self.cfg["vad_on"] = self.chk_vad.get()
        if self.engine:
            self.engine.gate_on = self.chk_gate.get()
            self.engine.vad_on = self.chk_vad.get()
        self._save()

    def _on_vol(self, v):
        self.cfg["volume"] = float(v)
        if self.engine:
            self.engine.volume = float(v)
        self._refresh_dynamic()
        if self._ready:
            self._save()

    def _save(self):
        self.cfg["input"] = self.cb_in.get()
        self.cfg["output"] = self.cb_out.get()
        self.cfg["gate_on"] = self.chk_gate.get()
        self.cfg["vad_on"] = self.chk_vad.get()
        save_cfg(self.cfg)

    # ------------------------------------------------------------------ صدا
    def _open_stream(self):
        if self.engine is None:
            return
        inp = self.cb_in.get()
        out = self.cb_out.get()
        in_dev = next((d for d in self.devices["inputs"] if d["name"] == inp), None)
        out_dev = next((d for d in self.devices["outputs"] if d["name"] == out), None)
        if in_dev is None or out_dev is None:
            raise RuntimeError("دستگاه صوتی انتخاب نشده است.")

        in_name = in_dev["name"]
        out_name = out_dev["name"]

        # پیدا کردن variantهای مختلف host API برای هر دستگاه (MME، DirectSound، WASAPI، WDM-KS)
        in_variants = []
        out_variants = []
        for i, d in enumerate(sd.query_devices()):
            cn = canonical_name(d["name"], active_endpoint_names())
            if cn and cn.lower() == in_name.lower() and d["max_input_channels"] > 0:
                in_variants.append(i)
            if cn and cn.lower() == out_name.lower() and d["max_output_channels"] > 0:
                out_variants.append(i)
        # اولویت: WASAPI → MME → DS → هر چه هست
        wasapi = self.wasapi_idx
        api_rank = {wasapi: 0} if wasapi is not None else {}
        for idx, h in enumerate(sd.query_hostapis()):
            if idx not in api_rank:
                api_rank[idx] = idx + 1
        in_variants.sort(key=lambda x: api_rank.get(sd.query_devices(x)["hostapi"], 99))
        out_variants.sort(key=lambda x: api_rank.get(sd.query_devices(x)["hostapi"], 99))
        if not in_variants:
            in_variants = [in_dev["id"]]
        if not out_variants:
            out_variants = [out_dev["id"]]

        log("input variants:", [(v, sd.query_devices(v)["name"], sd.query_devices(v)["hostapi"]) for v in in_variants])
        log("output variants:", [(v, sd.query_devices(v)["name"], sd.query_devices(v)["hostapi"]) for v in out_variants])

        info = sd.query_devices(in_dev["id"])
        fs = int(info["default_samplerate"])
        if fs > 96000:
            fs = 48000

        chans = (1, 2)
        last_err = None
        attempt_no = 0

        for iv in in_variants:
            for ov in out_variants:
                dev_pair = (iv, ov)
                for settings in ("wasapi", None):
                    attempt_no += 1
                    kw = dict(samplerate=fs, blocksize=256, dtype="float32",
                              channels=chans, latency="low", callback=self._audio_cb,
                              device=dev_pair)
                    if settings == "wasapi" and self.wasapi_idx is not None:
                        try:
                            kw["extra_settings"] = sd.WasapiSettings(exclusive=False)
                        except Exception:
                            continue
                    try:
                        st = sd.Stream(**kw)
                        st.start()
                        if st.samplerate is not None:
                            self.engine.fs = int(st.samplerate)
                            self.engine.hp = BiquadHighPass(int(st.samplerate), 90.0, 0.707)
                        host_name = sd.query_hostapis()[sd.query_devices(iv)["hostapi"]]["name"]
                        log("stream opened attempt", attempt_no,
                            "device", dev_pair, "hostapi", host_name, "fs", fs)
                        return st
                    except Exception as e:
                        last_err = e
                        log("stream attempt", attempt_no, "device", dev_pair,
                            "settings", settings, "failed:", repr(e))

        log_exc("_open_stream: all attempts failed")
        raise RuntimeError(str(last_err))

    def _audio_cb(self, indata, outdata, frames, time_info, status):
        try:
            if status:
                if status.input_overflow or status.output_underflow:
                    log("audio callback: warning -", status)
                    try:
                        self.cb_queue.put_nowait(("warn", 1))
                    except Exception:
                        pass
            y = self.engine.process(indata)
            if outdata.shape[1] >= 2:
                outdata[:, 0] = y
                outdata[:, 1] = y
            else:
                outdata[:, 0] = y
        except Exception as e:
            log_exc("_audio_cb")
            try:
                self.cb_queue.put_nowait(("err", str(e)))
            except Exception:
                pass

    def toggle_run(self):
        if self.stream is not None and self.engine and self.engine.running:
            self.stop_run()
        else:
            self._start_async()

    def _start_async(self):
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self):
        try:
            eng = AudioEngine(48000)
            eng.gate_on = self.chk_gate.get()
            eng.vad_on = self.chk_vad.get()
            eng.boost_db = float(self.cfg.get("boost_db", 0))
            eng.volume = float(self.cfg.get("volume", 0.9))
            eng.set_gate_db(float(self.cfg.get("gate_db", -45)))
            self.engine = eng
            st = self._open_stream()
            self.stream = st
            eng.running = True
            lat = st.latency
            ms = latency_ms(lat)
            eng.latency_ms = ms
            try:
                self.cb_queue.put_nowait(("started", 1))
            except Exception:
                pass
        except Exception as e:
            log_exc("_start_worker")
            try:
                self.cb_queue.put_nowait(("err", str(e)))
            except Exception:
                pass

    def stop_run(self):
        s = self.stream
        self.stream = None
        if self.engine:
            self.engine.running = False
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._refresh_status()
        self.btn_toggle.config(text=self._t("btn_toggle_start"))
        try:
            self.icon.menu = self._tray_menu()
        except Exception:
            pass

    def test_sound(self):
        """تست بلندگو: صدای کوتاه «دینگ»"""
        if self.engine is not None and self.engine.running:
            self.engine.play_ding()
            return
        out = next((d for d in self.devices["outputs"] if d["name"] == self.cb_out.get()), None)
        if out is None:
            return
        try:
            fs = int(sd.query_devices(out["id"])["default_samplerate"])
            if fs <= 0:
                fs = 48000
            sd.play(make_ding(fs), fs, device=out["id"])
        except Exception as e:
            try:
                messagebox.showerror(self._t("err_title"),
                                     f"{self._t('err_sound')}: {e}", parent=self.root)
            except Exception:
                pass

    # -------------------------------------------------------------- نوار وظیفه
    def _tray_menu(self):
        running = bool(self.stream is not None and self.engine and self.engine.running)
        if self.lang == "fa":
            txt_show, txt_toggle, txt_quit = "نمایش پنجره", "توقف" if running else "شروع", "خروج"
        else:
            txt_show, txt_toggle, txt_quit = "Show Window", "Stop" if running else "Start", "Quit"
        return pystray.Menu(
            pystray.MenuItem(txt_show, lambda: self.root.after(0, self.show_window), default=True),
            pystray.MenuItem(txt_toggle, lambda: self.root.after(0, self.toggle_run)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(txt_quit, lambda: self.root.after(0, self.quit_app)),
        )

    def _setup_tray(self):
        try:
            img = self._make_icon()
            self.icon = pystray.Icon(APP_NAME, img, APP_TITLE, menu=self._tray_menu())
            threading.Thread(target=self.icon.run, daemon=True).start()
            log("tray icon started")
        except Exception:
            log_exc("_setup_tray")

    def _make_icon(self):
        # اول از فایل icon.ico (بسته‌شده یا کنار EXE) بارگذاری کن
        p = self._icon_path()
        if p and os.path.isfile(p):
            try:
                img = Image.open(p).convert("RGBA")
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                log_exc("_make_icon load")
        # اگر فایل نبود، آیکون قبلی (رسم‌شده با PIL)
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 2, size - 2, size - 2], radius=14,
                            fill=(20, 30, 48, 255))
        cx = size / 2
        cy = size / 2 - 4
        r = size * 0.20
        d.ellipse([cx - r, cy - r + 4, cx + r, cy + r + 4], fill=(255, 255, 255, 255))
        d.line([cx, cy + r + 4, cx, cy + r + 12], fill=(255, 255, 255, 255), width=5)
        d.line([cx - r - 6, cy + r + 6, cx + r + 6, cy + r + 6], fill=(255, 255, 255, 255), width=5)
        d.line([cx, cy, cx, cy + 6], fill=(20, 30, 48, 255), width=3)
        return img

    @staticmethod
    def _icon_path():
        cands = []
        base = getattr(sys, "_MEIPASS", None)
        if base:
            cands.append(os.path.join(base, "icon.ico"))
        cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"))
        cands.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "icon.ico"))
        for p in cands:
            if os.path.isfile(p):
                return p
        return None

    def _set_window_icon(self):
        # آیکون پنجره و تسکبار را به آیکون خود برنامه تنظیم می‌کند (نه آیکون پیش‌فرض Tk)
        p = self._icon_path()
        if not p:
            return
        try:
            self.root.iconbitmap(p)
        except Exception:
            try:
                img = Image.open(p).convert("RGBA").resize((32, 32), Image.Resampling.LANCZOS)
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, photo)
                self._window_icon = photo  # نگهداری مرجع برای جلوگیری از جمع‌آوری
            except Exception:
                log_exc("_set_window_icon")

    def _show_about(self, event=None):
        card = "#1e2024"
        dlg = tk.Toplevel(self.root)
        dlg.title(self._t("app_title"))
        dlg.configure(bg=card)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text="Made By N2VID", bg=card, fg="#e5e7eb",
                 font=("Segoe UI", 13, "bold")).pack(padx=24, pady=(16, 8))
        tk.Label(dlg, text=self._t("about_text"), bg=card, fg="#a1a1aa",
                 justify="center", wraplength=420, font=("Segoe UI", 11)).pack(padx=24, pady=0)
        ttk.Button(dlg, style="Accent.TButton", text=self._t("close"),
                   command=dlg.destroy).pack(pady=(14, 14))

    def hide_to_tray(self):
        self.root.withdraw()
        if self.icon and not getattr(self.icon, "visible", False):
            try:
                self.icon.visible = True
            except Exception:
                pass

    def _setup_show_event(self):
        """ایجاد event ویندوز برای درخواست نمایش بین نمونه‌ها (Single Instanc)"""
        try:
            self._show_event = ctypes.windll.kernel32.CreateEventW(None, True, False, _SHOW_EVENT_NAME)
            threading.Thread(target=self._show_event_loop, daemon=True).start()
        except Exception:
            log_exc("_setup_show_event")

    def _show_event_loop(self):
        ev = getattr(self, "_show_event", None)
        while ev:
            try:
                r = ctypes.windll.kernel32.WaitForSingleObject(ev, 0xFFFFFFFF)  # INFINITE
                if r != 0:
                    return
                ctypes.windll.kernel32.ResetEvent(ev)
                try:
                    self.root.after(0, self._handle_show_request)
                except Exception:
                    return
            except Exception:
                return

    def _handle_show_request(self):
        # نمونه دوم اجرا شد → پنجره/ترهای ویندوز را جلو بیاور و فقط یک بوق بزن
        self.show_window()
        try:
            self.root.bell()
        except Exception:
            pass

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ------------------------------------------------------------------ حلقه
    def _tick(self):
        if self.root.winfo_exists():
            try:
                while True:
                    msg = self.cb_queue.get_nowait()
                    if msg[0] == "started":
                        self._refresh_status()
                        self.btn_toggle.config(text=self._t("btn_toggle_stop"))
                        try:
                            self.icon.menu = self._tray_menu()
                        except Exception:
                            pass
                    elif msg[0] == "err":
                        log("UI error shown:", msg[1])
                        messagebox.showerror(self._t("err_title"),
                                             f"{self._t('err_sound')}: {msg[1]}",
                                             parent=self.root)
                        self.stop_run()
            except queue.Empty:
                pass
            # نشانگر سطح صدا
            if getattr(self, "meter_cv", None) and self.meter_cv.winfo_exists():
                w = self.meter_cv.winfo_width()
                if w > 10:
                    in_lvl = self.engine.in_level if self.engine else 0.0
                    dbv = 20 * math.log10(max(float(in_lvl), 1e-9))
                    lvl = max(0.0, min(1.0, (dbv + 60.0) / 48.0))
                    self.meter_cv.coords(self.meter_rect, 0, 0, w * lvl, 18)
                    if lvl > 0.75:
                        self.meter_cv.itemconfig(self.meter_rect, fill="#ef4444")
                    elif lvl > 0.4:
                        self.meter_cv.itemconfig(self.meter_rect, fill="#f59e0b")
                    else:
                        self.meter_cv.itemconfig(self.meter_rect, fill="#22c55e")
                    # جای خط آستانه نویزگیر: مقیاس دسیبل مشابه نوار (−60 تا −12)
                    gd = float(self.cfg.get("gate_db", -45))
                    gx = max(0.0, min(1.0, (gd + 60.0) / 48.0)) * w
                    self.meter_cv.coords(self.meter_gate, gx, 1, gx, 17)
                if self.engine and self.engine.running:
                    if self.engine.voice_active:
                        vtxt = self._t("voice_talk")
                    elif self.engine.gate_on or self.engine.vad_on:
                        vtxt = self._t("voice_silent")
                    else:
                        vtxt = self._t("voice_silent_off")
                    vfg = "#22c55e" if self.engine.voice_active else "#6b7280"
                else:
                    vtxt = self._t("voice_off")
                    vfg = "#9a9aa2"
                if vtxt != self._voice_last:
                    self._voice_last = vtxt
                    self.lbl_voice.config(text=vtxt, foreground=vfg)
            self.root.after(40, self._tick)

    # ------------------------------------------------------------------ خروج
    def quit_app(self):
        log("quit requested")
        try:
            self._save()
            save_cfg(self.cfg)
        except Exception:
            log_exc("quit_app: saving config")
        self.stop_run()
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass
        log("app exited cleanly")


def latency_ms(lat):
    if isinstance(lat, (tuple, list)):
        v = lat[1] if len(lat) > 1 else lat[0]
    else:
        v = lat
    if isinstance(v, (int, float)):
        return v * 1000.0
    return None


def run_test(seconds=3):
    """تست کوتاه صدا برای بررسی کارکرد"""
    devs = list_devices()
    print("INPUTS:")
    for d in devs["inputs"]:
        print("  -", d["name"], f"(hostapi {d['hostapi']})")
    print("OUTPUTS:")
    for d in devs["outputs"]:
        print("  -", d["name"], f"(hostapi {d['hostapi']})")
    inp = pick_default(devs["inputs"], ["microphone"], devs["hostapis"], True)
    out = pick_default(devs["outputs"], ["headphones", "speakers"], devs["hostapis"], False)
    print("in:", inp["name"] if inp else None)
    print("out:", out["name"] if out else None)
    if not inp or not out:
        print("no devices")
        return
    eng = AudioEngine(48000)
    fs = int(sd.query_devices(inp["id"])["default_samplerate"])
    def cb(indata, outdata, frames, time_info, status):
        y = eng.process(indata)
        outdata[:, 0] = y
        outdata[:, 1] = y
    with sd.Stream(device=(inp["id"], out["id"]), samplerate=fs, blocksize=256,
                   dtype="float32", channels=(1, 2), latency="low",
                   callback=cb) as st:
        time.sleep(seconds)
        print("buffer ok. latency:", st.latency)


def main():
    setup_logging()
    log("=" * 60)
    log("app starting, argv =", sys.argv)
    try:
        if "--test" in sys.argv:
            run_test()
            return
        if not acquire_single_instance():
            log("another instance is already running; requested show & exiting")
            return
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception:
        log_exc("unhandled error in main")
        _show_crash_msg()
        sys.exit(1)


def _show_crash_msg():
    """نمایش پیام خطا و مسیر فایل لاگ وقتی خطای غیرمنتظره رخ دهد"""
    try:
        lang = load_cfg().get("lang", "fa")
        path = os.path.join(LOG_DIR, "micmonitor.log") if LOG_DIR else "?"
        if lang == "fa":
            msg = ("خطای غیرمنتظره رخ داد!\n"
                   "برای پیدا کردن مشکل، فایل لاگ را باز کنید:\n%s\n\n"
                   "متن همین پیام را برای پشتیبانی بفرستید." % path)
        else:
            msg = ("Unexpected error!\n"
                   "Check the log file to find the problem:\n%s\n\n"
                   "Send this message to support." % path)
        ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x10 | 0x1000)
    except Exception:
        pass


if __name__ == "__main__":
    main()