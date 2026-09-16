# AGENTS.md

## Project Overview
Microphone Booster — a Windows desktop app that takes microphone input, processes it in real time (noise gate, voice activity detection, boost, limiter), and plays it directly to the speakers with low latency.

The UI is a dark-themed, simple window (تقویت‌کننده میکروفون / Microphone Booster) with system-tray support. UI is **bilingual (Persian/English)** toggled by the corner EN/FA button; Persian = RTL layout, English = LTR. Status shows Active/Inactive.

## Tech Stack
- Python 3.12 (path: `C:\Users\N2VID\AppData\Local\Programs\Python\Python312`)
- `tkinter` (built-in) for the dark UI
- `sounddevice` (PortAudio) for low-latency WASAPI audio streaming
- `numpy` for real-time DSP
- `pystray` + `Pillow` for system tray icon/menu
- `PyInstaller` for building a single-file EXE
- `winreg` + `subprocess` (PowerShell `Get-PnpDevice`) for filtering to active audio devices
- `ctypes` for the single-instance named mutex and error dialog

## Key Files
- `mic_monitor.py` — the entire application (single file; do not split without a reason)
- `icon.ico` — app/exe icon
- `dist/Microphone Booster.exe` — the built standalone executable (deliverable)
- `build/` — PyInstaller intermediate output (regenerable)
- `dist/نحوه_استفاده.txt` — end-user Persian usage guide

## Commands
Run from project root `D:\Random Files\Projects\MIC`:

- Syntax check: `python -m py_compile mic_monitor.py`
- Quick audio smoke test (opens mic->speakers for 3 s, prints only active devices and achieved latency): `python mic_monitor.py --test`
- Launch the GUI: `python mic_monitor.py`
- Build the EXE:
  `pyinstaller --noconfirm --onefile --windowed --name "Microphone Booster" --icon icon.ico --add-data "icon.ico;." mic_monitor.py`
  → output `dist/Microphone Booster.exe`

## Architecture (mic_monitor.py)
- `App` class: builds the tkinter dark UI, tray icon/menu, `after()` polling loop (`_tick`, ~40 ms), worker thread for stream startup, command queue (`queue.Queue`) to marshal events back to the UI thread.
- **Bilingual (FA/EN):** `UI_TEXT` dictionary holds `(fa, en)` pairs; `App._t(key)` selects by `self.lang` (`cfg["lang"]`). `toggle_lang()` flips and calls `_refresh_ui()`. RTL: header/title pack sides, slider labels and the tray/quit buttons swap to the mirrored side; voice/status labels right-align via `anchor`.
- **Device filtering:** `active_endpoint_names()` runs one `Get-PnpDevice -Class AudioEndpoint` PowerShell call (Status=OK) → set of active friendly names. `list_devices()` keeps only PortAudio devices whose name matches an active endpoint (prefix match via `canonical_name()`), dedupes across host APIs, and keeps the WASAPI entry per device (lowest latency). No disabled/unplugged devices appear.
- **Single instance:** `acquire_single_instance()` creates a named mutex `Local\MicrophoneBooster_SingleInstance` via `ctypes`; on `ERROR_ALREADY_EXISTS` (code 183) it signals `Local\MicrophoneBooster_ShowEvent` so the first instance shows its window, then the new process exits silently (the old `_show_already_running()` MessageBox was removed).
- `AudioEngine`: real-time DSP. Run in the PortAudio callback. Per-block chain:
  1. `BiquadHighPass` — 2nd-order Butterworth high-pass @90 Hz to remove rumble/DC.
  2. Boost gain (`10**(boost_db/20)`) and volume.
  3. Noise gate with expander (ratio 2): RMS envelope follower; below threshold attenuates toward silence (linear gain ramp across the block to avoid zipper noise). Applied ONLY when `gate_on`; when off the signal passes untouched.
  4. Voice activity detection: smoothed envelope vs threshold → `engine.voice_active` drives the on-screen status. When `vad_on`, silence (below threshold) is fully muted to zero; when off, silence passes through.
  5. Soft peak limiter (smoothed, static threshold 0.951) to prevent clipping.
  - Input meter: `engine.in_level` tracks the raw pre-processing mic peak (attack 0.35 / release 0.05); the UI meter in `_tick` maps it logarithmically (−60 dB → 0, −12 dB → full) so the bar shows real mic loudness even when gating mutes the output.
  - Speaker test: `make_ding()` generates a short 3-tone "ding" (~0.3 s); when playback is running it is mixed inside the callback (`AudioEngine.play_ding()` → `process()`), otherwise `sd.play()` plays it on the selected output device.
  - `AudioEngine`, `BiquadHighPass` — helper classes.
- **Checkboxes:** `SquareCheck` (canvas-drawn hollow square = off, filled blue square + check = on) replaces ttk checkbuttons. `chk_gate` = noise gate enable, `chk_vad` = mute during silence (voice detect). `_on_checks()` applies the state live to the running engine and saves. Checkbox states are read with `.get()` / `.set()` (NOT ttk `state()`).
- Device selection helpers: `list_devices()`, `pick_default()` — prefer WASAPI host API devices, then name heuristics (`microphone` for input, `headphones`/`speakers` for output). Device IDs are NOT persisted; device names are.
- **Stream opening (`_open_stream`):** tries WASAPI shared mode first (`sd.WasapiSettings(exclusive=False)`), then plain, then default devices, then medium latency. Uses `blocksize=256`, `dtype='float32'`, `channels=(1, 2)`, `latency='low'`. Rebuilds `BiquadHighPass` with the actual stream samplerate after open.
  - CRITICAL gotcha (verified on this machine): the callback MUST be passed inside the `sd.Stream(...)` constructor (`callback=self._audio_cb`). Assigning `stream.callback = ...` AFTER creation silently never fires callbacks → stream opens with correct latency but zero audio flows. Same rule applies in `run_test()`.

## Conventions
- **Comments are Persian** (Farsi). Keep adding Persian comments in new code.
- UI strings live in `UI_TEXT` as `(fa, en)` pairs — never hardcode UI text outside it. Default language is Persian (`cfg["lang"]`).
- Combobox dropdowns use `DarkCombo.TCombobox` style (black background, white text) via `style.map` readonly states.
- No code comments for the sake of it — only where behavior is non-obvious (per repo style, minimal comments; here they are mostly Persian).
- Single-file app; prefer editing `mic_monitor.py` over creating new modules.
- Settings persist to `%APPDATA%\Microphone Booster\config.json` (JSON). `load_cfg()`/`save_cfg()` merge with `DEFAULT_CFG`. Device selection and all sliders are persisted; restore in `_restore_cfg()`.
- Close-to-tray behavior: `WM_DELETE_WINDOW` and `Esc` hide to tray, they don't quit. Real quit is via the tray menu "خروج" or the "خروج از برنامه" button.

## Important Nuances / Gotchas
- `pystray` requires a PIL image; `_make_icon()` loads `icon.ico` (bundled via `--add-data`, else next to the exe/script) and falls back to a drawn mic icon if missing. `pystray` must run in a non-main thread (daemon thread) — see `_setup_tray()`.
- The callback must never block or raise; exceptions are pushed to `self.cb_queue` for the UI thread to display via `messagebox` in `_tick()`.
- **Slider-creation gotcha (fixed):** `ttk.Scale` fires its `command` (→ `_on_boost/_on_gate/_on_vol` → `_save()`) at widget creation AND at any `scale.set()` (incl. inside `_restore_cfg`). Before the `_ready` guard existed, these startup saves overwrote `gate_on`/`vad_on` (and device names) with still-default values in `config.json`, so checkbox states reset to OFF on every restart. Fix: `App._ready = False` until `_restore_cfg()` finishes; slider/device handlers only `_save()` when `self._ready` is `True`.
- Tooltips: custom `ToolTip` class (Toplevel, appears ABOVE the widget, `Tip.TLabel` style). The EN/FA button's tooltip is intentionally the reverse of the active language ("تغییر زبان" when UI is EN, "Change Language" when UI is FA).
- WASAPI shared mode caps lowest latency around ~20–25 ms regardless of `blocksize`; do not chase lower values — it can cause dropouts.
- `App._tick()` reads `self.engine.in_level` and `self.engine.voice_active` directly (thread-safe floats/bools by GIL convention used here).
- After adding new stdlib/third-party imports, rebuild the EXE; PyInstaller is configured via CLI flags (see spec file `Microphone Booster.spec` regenerated by each build).
- Warning file `build/Microphone Booster/warn-Microphone Booster.txt` lists only benign cross-platform/optional modules — ignore it.

## Testing
- No formal test framework is used. Verify with:
  1. `python -m py_compile mic_monitor.py`
  2. `python mic_monitor.py --test` (lists only active devices; listens for obvious open/latency issues; prints achieved latency)
  3. Launch `dist/Microphone Booster.exe`, confirm process stays alive (GUI smoke test) — no crash within a few seconds indicates a healthy build.
  4. Single instance: launch a second `Microphone Booster.exe` while one is running — it must not open a second window and the first one comes to front.