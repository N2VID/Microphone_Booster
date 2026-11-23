# AGENTS.md

## Repo shape
- `mic_monitor.py` is the entire Windows app; keep changes there unless there is a strong reason to split it.
- `version.txt` supplies EXE metadata; keep it synced with `APP_VERSION` in code (both are `1.6.63`). `dist/`, `build/`, and `*.spec` are generated and gitignored.
- System-wide microphone boosting requires a virtual audio cable (README recommends VB-CABLE): system output → `CABLE Input`, app microphone → `CABLE Output`.
- No test framework, CI, lint, typecheck, pre-commit, or repo-local OpenCode config exists. Verification is manual.

## Commands (run from repo root)
- Install dev deps: `pip install numpy sounddevice pystray Pillow pyinstaller`
- Syntax check: `python -m py_compile mic_monitor.py`
- Audio smoke test: `python mic_monitor.py --test` — opens mic → speakers for 3 s, prints active devices and achieved latency; needs real/active audio devices.
- Launch GUI: `python mic_monitor.py`; internal `--autostart` flag launches hidden in the tray.
- Build EXE: `pyinstaller --noconfirm --onefile --windowed --name "Microphone Booster" --icon icon.ico --version-file version.txt --add-data "icon.ico;." mic_monitor.py` → `dist/Microphone Booster.exe`.
- Verify a build: syntax check, `--test`, launch the EXE and confirm it stays alive, then launch a second EXE and confirm no second window appears and the first comes to front.
- Settings: `%APPDATA%\Microphone Booster\config.json`; rotating log: `%APPDATA%\Microphone Booster\logs\micmonitor.log`.

## Runtime architecture and gotchas
- `App` owns the tkinter UI, a ~40 ms `after()` tick, a worker thread for stream startup, and a `queue.Queue` for worker/callback events. The audio callback must not block or raise; push errors to `cb_queue` for `_tick()` to show. `pystray` runs on a daemon thread.
- CRITICAL: pass `callback=...` inside `sd.Stream(...)`. Assigning `stream.callback` after construction silently produces no audio. Applies to `_open_stream()` and `run_test()`.
- `_open_stream()` tries WASAPI shared mode first, then plain device variants, then other host APIs, with `blocksize=256`, `float32`, `channels=(1, 2)`, `latency="low"`; rebuild the high-pass filter with the actual stream samplerate. WASAPI shared mode bottoms out around ~20–25 ms; do not chase lower values.
- DSP order: 90 Hz high-pass → boost/volume → noise gate + VAD → peak limiter. Gate/VAD thresholds use `in_level` (post-high-pass, pre-boost), which also drives the meter; VAD hard-mutes silence, and the gain ramp prevents zipper noise.
- `active_endpoint_names()` caches one PowerShell `Get-PnpDevice -Class AudioEndpoint` result (Status=OK, `CREATE_NO_WINDOW`); if it returns nothing, devices are unfiltered. `list_devices()` dedupes by canonical name and prefers WASAPI. Persist device **names**, never PortAudio IDs.
- The refresh button restarts the whole app to clear that device cache. For `--onefile`, restart must be sequential (wait for the old process to exit) and use `_clean_env()` to strip `_PYI_*`; otherwise the new instance can load a deleting `_MEI...` folder and fail on `python312.dll`.
- `SquareCheck` replaces ttk checkbuttons for DSP options; the new `ToggleSwitch` handles settings switches. Both use `.get()` / `.set()`, not ttk `state()`. `App._ready` stays false until `_restore_cfg()` finishes because `ttk.Scale` fires its command during creation and `.set()`; without the guard, startup saves overwrite saved settings.
- The gear is a 40×40 dark-blue canvas attached flush to the playback button inside `play_row` (no gap); the playback button takes the remaining width and is the primary large button. It toggles `options_card` without changing window width. Settings are `run_at_startup` and `auto_start` in config; both switches use the same blue theme and are mirrored in `_switches` for RTL/LTR.
- Windows startup uses HKCU `Software\Microsoft\Windows\CurrentVersion\Run` value `Microphone Booster`: `<exe> --autostart`. The registry is the source of truth for the switch and its command path is refreshed on launch. `--autostart` hides the window and skips the show-existing signal; a normal launch opens the window. `auto_start` starts playback on both paths.
- Close button and `Esc` hide to tray; quit only via tray menu or the Quit button. A second normal process signals the named show event, bringing the first window forward, then exits silently.
- UI: Persian is default/RTL, English is LTR. Static strings live in `UI_TEXT` as `(fa, en)` pairs; dynamic slider labels are formatted in `_refresh_dynamic()` and must be updated in both languages. The window title is always `Microphone Booster`; the bilingual header text uses `app_title`. Running state is shown by turning the header title green, not by a status label.
- Window height auto-hugs content in `_autosize()`; window background and Windows 11 titlebar are pure black. There is no watermark/decorative canvas — don’t re-add glyphs.
- New comments should be in Persian, matching the existing style; keep them only where behavior is non-obvious.
