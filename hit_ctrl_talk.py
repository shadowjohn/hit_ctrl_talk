# -*- coding: utf-8 -*-
"""Push-to-talk speech input for Windows.

Hold either Ctrl key by itself for a short time to begin recording.
Release all Ctrl keys to stop, transcribe with faster-whisper, convert
simplified Chinese to traditional Chinese, then paste/type the text into
the active application.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import queue
import re
import sys
import threading
import time
import the_icon
import base64
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

try:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    import keyboard
    import numpy as np
    import php
    import pyperclip
    import pythoncom
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from opencc import OpenCC
    from traybar import SysTrayIcon
except ImportError as exc:
    print(
        "Missing dependency: %s\n"
        "Please install dependencies with:\n"
        "  pip install -r requirements.txt" % exc,
        file=sys.stderr,
    )
    raise

AUTHOR_NAME = "羽山秋人(https://3wa.tw)"
VERSION = "0.0.1"
CTRL_NAMES = {"ctrl", "left ctrl", "right ctrl"}
ERROR_ALREADY_EXISTS = 183
APP_MUTEX = None
PHP = php.kit()


def is_windows() -> bool:
    return PHP.is_win()


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def now() -> float:
    return time.monotonic()


def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return PHP.pwd()


def get_model_dir() -> str:
    return os.path.join(get_app_dir(), "models")


def get_icon_ico_path() -> str:
    return os.path.join(get_app_dir(), "icon.ico")


def get_mutex_name() -> str:
    app_dir = get_app_dir().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", app_dir)
    return "Local\\hit_ctrl_talk_%s" % normalized


def show_message_box(title: str, message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000040)


def is_missing_vad_asset_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "silero_vad_v6.onnx" in message and "file doesn't exist" in message


def ensure_single_instance() -> bool:
    global APP_MUTEX
    if not is_windows():
        return True

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p

    mutex_name = get_mutex_name()
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    if not handle:
        raise ctypes.WinError()

    APP_MUTEX = handle
    if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(handle)
        APP_MUTEX = None
        return False
    return True


def release_single_instance() -> None:
    global APP_MUTEX
    if APP_MUTEX:
        ctypes.windll.kernel32.CloseHandle(APP_MUTEX)
        APP_MUTEX = None


@dataclass
class AppConfig:
    model_name: str
    paste_mode: str
    language: str
    device_preference: str
    device_index: Optional[int]
    hold_ms: int
    sample_rate: int = 16000
    channels: int = 1
    min_record_seconds: float = 0.20
    vad_filter: bool = True
    debug_audio: bool = False
    model_dir: str = ""


@dataclass
class TranscriptionResult:
    text: str
    device_used: str
    used_vad: bool


@dataclass
class AudioStats:
    duration: float
    peak: float
    rms: float
    samples: int


class AudioRecorder:
    def __init__(self, sample_rate: int, channels: int, device_index: Optional[int]) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self._stream: Optional[sd.InputStream] = None
        self._frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._started_at: Optional[float] = None

    def start(self) -> None:
        with self._lock:
            self._frames = []
            self._started_at = now()
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=self.device_index,
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, callback_time, status) -> None:  # pragma: no cover - callback
        if status:
            print("[audio] %s" % status, flush=True)
        with self._lock:
            self._frames.append(indata.copy())

    def stop(self) -> tuple[Optional[np.ndarray], float]:
        with self._lock:
            stream = self._stream
            self._stream = None
            started_at = self._started_at
            self._started_at = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        duration = max(0.0, now() - started_at) if started_at else 0.0
        with self._lock:
            if not self._frames:
                return None, duration
            audio = np.concatenate(self._frames, axis=0).reshape(-1)
            self._frames = []
        return audio, duration

    def discard(self) -> None:
        audio, _ = self.stop()
        if audio is not None:
            del audio


def compute_audio_stats(audio: np.ndarray, duration: float) -> AudioStats:
    if audio.size == 0:
        return AudioStats(duration=duration, peak=0.0, rms=0.0, samples=0)
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(np.square(audio))))
    return AudioStats(duration=duration, peak=peak, rms=rms, samples=int(audio.size))


class ModelManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._model = None
        self._device_used: Optional[str] = None

    def warmup(self) -> str:
        model, device_used = self._get_model()
        del model
        return device_used

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        try:
            model, device_used = self._get_model()
            return self._transcribe_with_model(
                model=model,
                device_used=device_used,
                audio=audio,
                vad_filter=self.config.vad_filter,
            )
        except Exception as exc:
            if self.config.vad_filter and is_missing_vad_asset_error(exc):
                print("[model] VAD asset missing, retrying without VAD: %s" % exc, flush=True)
                model, device_used = self._get_model()
                return self._transcribe_with_model(
                    model=model,
                    device_used=device_used,
                    audio=audio,
                    vad_filter=False,
                )
            if self._device_used == "cuda" and self.config.device_preference != "cuda":
                print("[model] cuda inference failed, falling back to cpu: %s" % exc, flush=True)
                self._reset_model()
                model, device_used = self._load_specific_model("cpu", "int8")
                retry_vad_filter = self.config.vad_filter and not is_missing_vad_asset_error(exc)
                return self._transcribe_with_model(
                    model=model,
                    device_used=device_used,
                    audio=audio,
                    vad_filter=retry_vad_filter,
                )
            raise

    def _transcribe_with_model(
        self,
        model,
        device_used: str,
        audio: np.ndarray,
        vad_filter: bool,
    ) -> TranscriptionResult:
        segments, info = model.transcribe(
            audio,
            language=self.config.language,
            vad_filter=vad_filter,
        )
        text = clean_text("".join(segment.text for segment in segments))
        if text or not vad_filter:
            return TranscriptionResult(text=text, device_used=device_used, used_vad=vad_filter)

        print("[model] empty result with VAD enabled, retrying without VAD...", flush=True)
        segments, info = model.transcribe(
            audio,
            language=self.config.language,
            vad_filter=False,
        )
        text = clean_text("".join(segment.text for segment in segments))
        return TranscriptionResult(text=text, device_used=device_used, used_vad=False)

    def _get_model(self):
        with self._lock:
            if self._model is not None:
                return self._model, self._device_used

            pass

        last_error: Optional[Exception] = None
        for device, compute_type in self._device_candidates():
            try:
                model, device_used = self._load_specific_model(device, compute_type)
                return self._model, self._device_used
            except Exception as exc:  # pragma: no cover - depends on local runtime
                last_error = exc
                print(
                    "[model] failed on %s (%s): %s" % (device, compute_type, exc),
                    flush=True,
                )

        raise RuntimeError("Unable to load whisper model: %s" % last_error)

    def _device_order(self) -> Sequence[str]:
        if self.config.device_preference == "cuda":
            return ("cuda",)
        if self.config.device_preference == "cpu":
            return ("cpu",)
        return ("cuda", "cpu")

    def _device_candidates(self) -> Sequence[Tuple[str, str]]:
        candidates: List[Tuple[str, str]] = []
        for device in self._device_order():
            if device == "cuda":
                candidates.extend(
                    [
                        ("cuda", "float16"),
                        ("cuda", "int8_float16"),
                        ("cuda", "int8"),
                    ]
                )
            else:
                candidates.append(("cpu", "int8"))
        return candidates

    def _load_specific_model(self, device: str, compute_type: str):
        print(
            "[model] loading '%s' on %s (%s)..."
            % (self.config.model_name, device, compute_type),
            flush=True,
        )
        model = WhisperModel(
            self.config.model_name,
            device=device,
            compute_type=compute_type,
            download_root=self.config.model_dir,
        )
        with self._lock:
            self._model = model
            self._device_used = device
        print("[model] ready on %s (%s)" % (device, compute_type), flush=True)
        return self._model, self._device_used

    def _reset_model(self) -> None:
        with self._lock:
            self._model = None
            self._device_used = None


class TextInjector:
    def __init__(self, paste_mode: str) -> None:
        self.paste_mode = paste_mode
        self._inject_lock = threading.Lock()

    def inject(self, text: str) -> None:
        with self._inject_lock:
            if self.paste_mode == "unicode":
                self._send_unicode(text)
                return
            self._paste_via_clipboard(text)

    def _paste_via_clipboard(self, text: str) -> None:
        original = None
        try:
            original = pyperclip.paste()
        except Exception:
            original = None

        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.press_and_release("ctrl+v")

        if original is not None:
            injected_text = text

            def restore_clipboard(old_text: str, expected_text: str) -> None:
                time.sleep(0.3)
                try:
                    current = pyperclip.paste()
                    if current == expected_text:
                        pyperclip.copy(old_text)
                except Exception:
                    pass

            threading.Thread(
                target=restore_clipboard,
                args=(original, injected_text),
                daemon=True,
            ).start()

    def _send_unicode(self, text: str) -> None:
        if not is_windows():
            raise RuntimeError("Unicode input mode currently supports Windows only.")

        user32 = ctypes.windll.user32
        send_input = user32.SendInput

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]

            _anonymous_ = ("_input",)
            _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]

        input_keyboard = 1
        keyeventf_unicode = 0x0004
        keyeventf_keyup = 0x0002

        for char in text:
            utf16_units = char.encode("utf-16-le")
            for index in range(0, len(utf16_units), 2):
                code_unit = int.from_bytes(utf16_units[index:index + 2], "little")
                key_down = INPUT(
                    type=input_keyboard,
                    ki=KEYBDINPUT(
                        wVk=0,
                        wScan=code_unit,
                        dwFlags=keyeventf_unicode,
                        time=0,
                        dwExtraInfo=None,
                    ),
                )
                key_up = INPUT(
                    type=input_keyboard,
                    ki=KEYBDINPUT(
                        wVk=0,
                        wScan=code_unit,
                        dwFlags=keyeventf_unicode | keyeventf_keyup,
                        time=0,
                        dwExtraInfo=None,
                    ),
                )
                inputs = (INPUT * 2)(key_down, key_up)
                sent = send_input(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
                if sent != 2:
                    raise ctypes.WinError()


class CtrlTalkApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.opencc = OpenCC("s2t")
        self.recorder = AudioRecorder(
            sample_rate=config.sample_rate,
            channels=config.channels,
            device_index=config.device_index,
        )
        self.model_manager = ModelManager(config)
        self.injector = TextInjector(config.paste_mode)
        self._lock = threading.Lock()
        self._pressed_ctrls: Set[str] = set()
        self._candidate_id = 0
        self._state = "idle"
        self._block_until_release = False
        self._work_queue: queue.Queue = queue.Queue()
        self._hook = None
        self._systray = None
        self._stop_event = threading.Event()

    def run(self) -> None:
        if self.config.debug_audio:
            self._print_input_devices()
        self._start_tray_icon()
        self._start_worker()
        self._start_model_warmup()
        print("[ready] paste_mode=%s" % self.config.paste_mode, flush=True)
        print("[ready] model_dir=%s" % self.config.model_dir, flush=True)
        print(
            "[ready] hold either Ctrl alone for %dms to talk."
            % self.config.hold_ms,
            flush=True,
        )

        self._hook = keyboard.hook(self._on_keyboard_event, suppress=False)
        while not self._stop_event.is_set():
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
        self.shutdown()

    def _start_worker(self) -> None:
        worker = threading.Thread(target=self._worker_loop, daemon=True)
        worker.start()

    def _start_model_warmup(self) -> None:
        def warmup() -> None:
            try:
                device_used = self.model_manager.warmup()
                print("[model] background warmup ready on %s" % device_used, flush=True)
            except Exception as exc:
                print("[model] background warmup skipped: %s" % exc, flush=True)

        threading.Thread(target=warmup, daemon=True).start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        if self._systray is not None:
            try:
                self._systray.shutdown()
            except Exception:
                pass
            self._systray = None
        self._work_queue.put(None)
        try:
            self.recorder.discard()
        except Exception:
            pass
        self._release_single_instance()

    def _release_single_instance(self) -> None:
        release_single_instance()

    def _print_input_devices(self) -> None:
        try:
            devices = sd.query_devices()
        except Exception as exc:
            print("[audio] unable to list devices: %s" % exc, flush=True)
            return

        print("[audio] available input devices:", flush=True)
        for index, device in enumerate(devices):
            if int(device.get("max_input_channels", 0)) <= 0:
                continue
            marker = "*" if self.config.device_index == index else " "
            print(
                "[audio] %s %d: %s (inputs=%s, default_sr=%s)"
                % (
                    marker,
                    index,
                    device.get("name", "unknown"),
                    device.get("max_input_channels", 0),
                    device.get("default_samplerate", "?"),
                ),
                flush=True,
            )

    def _start_tray_icon(self) -> None:
        icon_path = get_icon_ico_path()
        if not os.path.isfile(icon_path):
            #print("[tray] icon.ico not found: %s" % icon_path, flush=True)
            #return
            # 從 the_icon 模組中提取 icon.ico 資源並寫入到磁盤
            raw_data = base64.b64decode(str(the_icon.the_ico_icon))            
            #生小圖，等會載入完就移除            
            try:
                PHP.file_put_contents(icon_path,raw_data,False)      
            except e:      
                pass

        menu_options = (
            ("關於 (About)", None, [self._on_tray_about]),
            ("結束 (Quit)", None, [self._on_tray_quit]),
        )
        self._systray = SysTrayIcon(
            icon_path,
            "按 Ctrl 講話 (Hold Ctrl to Talk) BY \n%s\nV%s" % (AUTHOR_NAME, VERSION),
            menu_options,
        )
        self._systray.start()
        print("[tray] using icon file: %s" % icon_path, flush=True)
        print("[tray] icon visible.", flush=True)

    def _on_tray_about(self, systray=None, params=None) -> None:
        self._show_about()

    def _on_tray_quit(self, systray=None, params=None) -> None:
        print("[quit] tray menu requested exit.", flush=True)
        self._stop_event.set()

    def _show_about(self) -> None:
        global AUTHOR_NAME
        global VERSION
        message = (
            "按著 Ctrl 然後講\n\n"
            "作者：%s\n"
            "版本：V%s\n"
            "單獨按住 Ctrl 可開始說話。\n"
            "放開 Ctrl 後會進行辨識並貼上文字。\n\n"
            "模型：%s\n"
            "貼上模式：%s\n"
            "模型資料夾：%s"
        ) % (
            AUTHOR_NAME,
            VERSION,
            self.config.model_name,
            self.config.paste_mode,
            self.config.model_dir,
        )
        show_message_box("關於 按著 Ctrl 然後講", message)

    def _worker_loop(self) -> None:
        while True:
            item = self._work_queue.get()
            if item is None:
                return
            audio, duration = item
            self._process_audio(audio, duration)

    def _on_keyboard_event(self, event) -> None:
        name = (event.name or "").lower()
        if not name:
            return

        is_down = event.event_type == "down"
        is_up = event.event_type == "up"
        is_ctrl = name in CTRL_NAMES

        with self._lock:
            if is_ctrl and is_down:
                self._handle_ctrl_down(name)
                return

            if is_ctrl and is_up:
                self._handle_ctrl_up(name)
                return

            if is_down and self._pressed_ctrls:
                self._handle_non_ctrl_during_ctrl(name)

    def _handle_ctrl_down(self, name: str) -> None:
        self._pressed_ctrls.add(name)
        if self._block_until_release:
            return
        if self._state != "idle":
            return

        self._state = "candidate"
        self._candidate_deadline = now() + (self.config.hold_ms / 1000.0)
        self._candidate_id += 1
        candidate_id = self._candidate_id
        print("[candidate] Ctrl held, waiting %dms..." % self.config.hold_ms, flush=True)
        timer = threading.Timer(self.config.hold_ms / 1000.0, self._candidate_timer_fired, args=(candidate_id,))
        timer.daemon = True
        timer.start()

    def _handle_ctrl_up(self, name: str) -> None:
        self._pressed_ctrls.discard(name)

        if self._pressed_ctrls:
            return

        if self._state == "candidate":
            self._state = "idle"
            print("[idle] Ctrl released before recording started.", flush=True)
        elif self._state == "recording":
            self._state = "processing"
            audio, duration = self.recorder.stop()
            if audio is None or duration < self.config.min_record_seconds:
                self._state = "idle"
                print("[skip] recording too short or empty.", flush=True)
            else:
                print("[processing] transcribing %.2fs..." % duration, flush=True)
                self._work_queue.put((audio, duration))
        elif self._state == "cancelled":
            self._state = "idle"
            print("[idle] keyboard shortcut path restored.", flush=True)

        self._block_until_release = False

    def _handle_non_ctrl_during_ctrl(self, name: str) -> None:
        if self._state == "candidate":
            self._state = "cancelled"
            self._block_until_release = True
            print("[cancelled] '%s' used with Ctrl, treating as normal shortcut." % name, flush=True)
            return

        if self._state == "recording":
            self.recorder.discard()
            self._state = "cancelled"
            self._block_until_release = True
            print("[cancelled] '%s' pressed during recording, discarding audio." % name, flush=True)

    def _candidate_timer_fired(self, candidate_id: int) -> None:
        with self._lock:
            if candidate_id != self._candidate_id:
                return
            if self._state != "candidate":
                return
            if self._block_until_release:
                return
            if not self._pressed_ctrls:
                return
            try:
                self.recorder.start()
            except Exception as exc:
                self._state = "idle"
                self._block_until_release = True
                print("[error] unable to start recording: %s" % exc, flush=True)
                return
            self._state = "recording"
            print("[recording] listening...", flush=True)

    def _process_audio(self, audio: np.ndarray, duration: float) -> None:
        try:
            stats = compute_audio_stats(audio, duration)
            print(
                "[audio] duration=%.2fs samples=%d peak=%.4f rms=%.4f"
                % (stats.duration, stats.samples, stats.peak, stats.rms),
                flush=True,
            )
            if stats.rms < 0.003:
                print(
                    "[audio] input level is very low. Check microphone device or speak louder.",
                    flush=True,
                )

            result = self.model_manager.transcribe(audio)
            text = clean_text(result.text)
            if not text:
                print(
                    "[skip] no transcription result. Try --debug-audio or --no-vad and verify input device.",
                    flush=True,
                )
                return

            text = clean_text(self.opencc.convert(text))
            print("[result:%s vad=%s] %s" % (result.device_used, result.used_vad, text), flush=True)
            self.injector.inject(text)
        except Exception as exc:
            print("[error] transcription failed: %s" % exc, flush=True)
        finally:
            with self._lock:
                self._state = "idle"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hold Ctrl to talk, release Ctrl to transcribe.")
    parser.add_argument("--model", default="small", choices=["base", "small", "medium"])
    parser.add_argument("--paste-mode", default="clipboard", choices=["clipboard", "unicode"])
    parser.add_argument("--language", default="zh")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--device-index", default=None, type=int)
    parser.add_argument("--hold-ms", default=100, type=int)
    parser.add_argument("--no-vad", action="store_true")
    parser.add_argument("--debug-audio", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--model-dir", default=get_model_dir())
    return parser


def main() -> int:
    if not is_windows():
        print("This tool currently targets Windows.", file=sys.stderr)
        return 1
    if not ensure_single_instance():
        print("hit_ctrl_talk is already running.", file=sys.stderr)
        return 0

    try:
        args = build_parser().parse_args()
        if args.list_devices:
            try:
                print(sd.query_devices())
                return 0
            except Exception as exc:
                print("Unable to query audio devices: %s" % exc, file=sys.stderr)
                return 1

        config = AppConfig(
            model_name=args.model,
            paste_mode=args.paste_mode,
            language=args.language,
            device_preference=args.device,
            device_index=args.device_index,
            hold_ms=max(50, args.hold_ms),
            vad_filter=not args.no_vad,
            debug_audio=args.debug_audio,
            model_dir=os.path.abspath(args.model_dir),
        )
        app = CtrlTalkApp(config)
        app.run()
        return 0
    finally:
        release_single_instance()


if __name__ == "__main__":
    raise SystemExit(main())
